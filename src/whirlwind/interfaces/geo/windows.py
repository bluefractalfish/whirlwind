"""whirlwind.interfaces.geo.windows 


    raster, tspec - > >WindowPlan< -> TesselationPlan 
    
    raster, PlanRow -> >ReadWindow< -> Tile

    TileArray, TileMetadata -> >WriteShard<  -> .npy, .json Tile shards 


"""

import numpy as np 
import rasterio 
from rasterio import Affine 
from rasterio.io import DatasetReader 
from rasterio.windows import Window
from rasterio.windows import bounds as window_bounds 
from rasterio.windows import transform as window_transform 


from dataclasses import dataclass 
from pathlib import Path 
from typing import Any, Dict, List, Tuple, Optional, Sequence, Iterable 
from osgeo import gdal, osr 
from typing import Iterator, Tuple


from whirlwind.filetrees.files import File, RasterFile
from whirlwind.geometry.tile import GeoData, TileRead, Tile 
from whirlwind.io.planio import PlanRow
from whirlwind.specs import TSpec 

@dataclass 
class WindowPlan:
    """ 
        this interface layer between the filesystem and gdal provides 
        window related functions, specifically extracting the 
        window metadata needed to plan a tiling operation, and reading 
        these windows once a plan has been determined 
        
        Inputs 
        -------- 
        path/to/raster 
        TSpec
            - tile_size 
            - stride 
            - drop_partials 

        Outputs 
        -------- 
        Iterator[Tuple[int*6]] 
            -> row_index, col_index, x_pixel, y_pixel, height_in_pixels, width_in_pixels 
        
        Example Usage 
        --------------- 

        reader = WindowPlan(p, spec)
            for ri, ci, x, y, h, w in reader.get_grid():
                row = PlanRow(row_i=ri, col_i=ci, 
                              x=x, y=y, w=w, h=h)
                planio.append_csv(row)
    """

    def __init__(self, path: str | Path, spec: TSpec) -> None:
        _import_osgeo() 

        ## open dataset briefly for height and width, then close 
        ds = gdal.Open(path, gdal.GA_ReadOnly)
        if ds is None:
            raise RuntimeError(...)
        self.max_x = ds.RasterXSize 
        self.max_y = ds.RasterYSize 
        ds = None 
        #######################################################

        self.src_path = Path(path).expanduser().resolve()
        self.spec = spec

    
    def get_grid(self) -> Iterator[Tuple[int, int, int, int, int, int]]:
        """ core logic for WindowPlan 
            
            using height and width of input raster and a tiling spec, computes for a raster window the 
            row/column index, the x and y coordinate in pixel space, and the width and height in pixel space 

        """
        max_x = self.max_x
        max_y = self.max_y 
        tile_size = self.spec.tile_size
        stride = self.spec.stride 

        if self.spec.drop_partial:
            x_stops = range(0, max_x - tile_size +1, stride)
            y_stops = range(0, max_y - tile_size +1, stride) 
        else:
            x_stops = range(0, max_x, stride)
            y_stops = range(0, max_y, stride)

        for ri, y in enumerate(y_stops): 
            for ci, x in enumerate(x_stops):
                w = tile_size if (x + tile_size <= max_x) else (max_x - x)
                h = tile_size if (y + tile_size <= max_y) else (max_y - y)
                if self.spec.drop_partial and (w != tile_size or h != tile_size):
                    continue
                yield ri, ci, x, y, w, h 



class WindowReader:  
    """ 
        an interface layer between filesystem, tile plan, tiles, and gdal. provides 
        the functionality required to read window 
        rom window
        Inputs 
        -------- 
        takes in a raster and a PlanRow
        
        Outputs 
        --------
        returns either a Tile from a single row (tile_from_row)
        or an iterable list of Tiles (tiles_from_rows)

        Example Usage 
        -------- 
        read all rows: 
        with WindowReader(raster_path) as reader: 
            for tile in reader.tiles_from_rows(planio.read_csv(),
                                                masked = True, 
                                                fill_value=0.0, 
                                                out_dtype="float32"): 
                array = tile.read.array 
                bounds = tile.geo.bounds 
                transform = tile.geo.transform 

        read one row as a tile: 
        row = PlanRow(row_i=0, col_i=1, x=0, y=512, w=512, h=512)

        with WindowReader(path/to/mosaic.tif) as reader: 
            tile = reader.tile_from_row( row, ...) 

        tile.shape, etc 

        Responsibilities 
        --------
            - open raster once as ds 
            - deterministically reconstruct rasterio.Window from PlanRow 
            - read one tile or iterate over array of tiles, return Tile or [Tile] 
            - avoid full raster read 
    """


    def __init__(self, path: str | Path, spec: Optional[TSpec]=None) -> None: 
        _import_osgeo()
        self.src_path = Path(path).expanduser().resolve()
        self.raster = RasterFile(self.src_path)
        self.spec = spec 
        self._ds: DatasetReader | None=None  
    
    def __enter__(self) -> "WindowReader":
        self._ds = rasterio.open(self.src_path)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._ds is not None:
            self._ds.close()
            self._ds = None 

    @property 
    def ds(self) -> DatasetReader: 
        if self._ds is None:
            raise RuntimeError("dataset is not open")
        return self._ds 

    @staticmethod 
    def to_window(row: PlanRow) -> Window: 
        return Window( 
                      col_off=int(row.x),
                      row_off=int(row.y),
                      width=int(row.w),
                      height=int(row.h)
                      )

    def validate_row(self, row: PlanRow) -> None: 
        if row.x < 0 or row.y < 0: 
            raise ValueError(f"negative window offset: x = {row.x}, y = {row.y}")

        if row.w <= 0 or row.h <= 0:
            raise ValueError(f"non-positive window size: w={row.w}, h={row.h}")

        if row.x + row.w > self.ds.width:
            raise ValueError(
                f"window exceeds raster width: x={row.x}, w={row.w}, raster_width={self.ds.width}"
            )

        if row.y + row.h > self.ds.height:
            raise ValueError(
                f"window exceeds raster height: y={row.y}, h={row.h}, raster_height={self.ds.height}"
            )

    def get_transform(self, row:PlanRow):
        win = self.to_window(row)
        return window_transform(win, self.ds.transform)

    def get_bounds(self, row: PlanRow) -> tuple[float, float, float, float]: 
        win = self.to_window(row)
        return window_bounds(win, self.ds.transform)
    
    def get_geodata(self, row: PlanRow) -> GeoData: 
        crs_str = self.ds.crs.to_string() if self.ds.crs else ""
        return GeoData(
                transform = self.get_transform(row),
                bounds = self.get_bounds(row), 
                crs = crs_str 
                )
    def read_data(
            self,
            row: PlanRow, 
            *, 
            masked: bool = True, 
            fill_value: float | None = None, 
            out_dtype: str | np.dtype | None = None, 
            bands: Iterable[int] | None = None, 
            ) -> TileRead: 
        self.validate_row(row)
        win = self.to_window(row)
        indexes = None if bands is None else list(bands)
        
        #######################################
        #### core reading call from Dataset ###
        array = self.ds.read(
                indexes=indexes, 
                window=win, 
                masked=masked, 
                out_dtype=out_dtype
                ) 
        #######################################
        if array.ndim == 2:
            array = array[np.newaxis, :, :]

        was_masked = bool(np.ma.isMaskedArray(array))

        if fill_value is not None and np.ma.isMaskedArray(array):
            array = np.ma.filled(array, fill_value)

        return TileRead(
                row=row,
                array=array, 
                masked=was_masked, 
                band_count=int(array.shape[0]),
                dtype=str(array.dtype)
                )

    def tile_from_row(
            self, 
            row: PlanRow, 
            *, 
            masked: bool = True, 
            fill_value: float | None = None, 
            out_dtype: str | np.dtype | None = None, 
            bands: Iterable[int] | None = None,
            tile_id: str | None = None, 
            source: RasterFile | None = None,
            ) -> Tile:

            read = self.read_data(
                row,
                masked=masked,
                fill_value=fill_value,
                out_dtype=out_dtype,
                bands=bands,
            )

            geo = self.get_geodata(row)

            return Tile(
                plan=row,
                read=read,
                geo=geo,
                source=source,
                tile_id=tile_id,
            )

    def tiles_from_rows(
        self,
        rows: Iterable[PlanRow],
        *,
        masked: bool = True,
        fill_value: float | None = None,
        out_dtype: str | np.dtype | None = None,
        bands: Iterable[int] | None = None,
        source: RasterFile | None = None ) -> Iterator[Tile]:
        for row in rows:
            yield self.tile_from_row(
                row,
                masked=masked,
                fill_value=fill_value,
                out_dtype=out_dtype,
                bands=bands,
                source=source,
            )

def _import_osgeo():
    try:
        from osgeo import gdal, osr 
    except Exception as exc:
        raise RuntimeError(
        "GDAL required") from exc 
    try: 
        gdal.UseExceptions()
    except Exception:
        pass 
    return gdal, osr 



