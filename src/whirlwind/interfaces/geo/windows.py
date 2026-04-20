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
from typing import Any, Dict, List, Tuple, Optional, Sequence 
from osgeo import gdal, osr 
from typing import Iterator, Tuple


from whirlwind.filetrees.files import File, RasterFile
from whirlwind.geometry.tile import GeoData, TileRead, Tile 
from whirlwind.specs import TSpec 

@dataclass 
class WindowPlan:
    """ 
        this interface layer between the filesystem and gdal provides 
        window related functions, specifically extracting the 
        window metadata needed to plan a tiling operation, and reading 
        these windows once a plan has been determined 
    """
    path: Path 
    spec: TSpec 
    # store maxx, maxy so dataset is opened briefly 
    max_x: int 
    max_y: int 

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

        self.path = Path(path).expanduser().resolve()
        self.spec = spec

    
    def get_grid(self) -> Iterator[Tuple[int, int, int, int, int, int]]:
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
        this is an interface layer between filesystem, tile plan, tiles, and gdal. provides 
        the functionality required to read window 
            
        takes in a raster and a PlanRow and returns the tile array and tile metadata 
        the output of this is used to write shards

        responsibilities: 
            - open raster once as ds 
            - deterministically reconstruct rasterio.Window from PlanRow 
            - read one tile or iterate over array of tiles 
            - avoid full raster read 
    """

    path: Path 
    raster: RasterFile 
    spec: Optional[TSpec]

    def __init__(self, path: str | Path, spec: Optional[TSpec]=None) -> None: 
        _import_osgeo()
        self.path = Path(path).expanduser().resolve()
        self.raster = RasterFile(self.path)
        self.spec = spec 
        self._ds: DatasetReader | None=None  
    
    def __enter__(self) -> "WindowReader":
        self._ds = rasterio.open(self.path)
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



