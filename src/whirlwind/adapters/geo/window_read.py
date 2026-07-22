


from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import rasterio
from rasterio.io import DatasetReader
from rasterio.windows import Window
from rasterio.windows import bounds as window_bounds
from rasterio.windows import transform as window_transform

from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from whirlwind.filesystem.files import RasterFile
from whirlwind.domain.tile import TileGeoData, Tile, TileRead
from whirlwind.domain.plannedwindow import PlannedWindow

class RasterioWindowReader:
    """ given a path to a raster and a set of PlannedWindows to describe intended windows, 
        cut raster into a set of Windows 

        PUBLIC 
        -------- 
        with RasterioWindowReader(path: str | Path) as reader 

            contains 
            --------- 
            path: Path 
            source: RasterFile (with georefs)

            methods 
            --------- 
            @property 
            ds -> DatasetReader 
            to_window(row: PlannedWindow) -> Window 
            validate_row(row:PlannedWindow) -> None 
            geodata(row: PlannedWindow) -> TileTileGeoData
        

    """
    def __init__(self,
            path: str | Path,
            masked: bool,
            fill: float | int | None,
            *,
            canonical_path: str | Path | None = None,
            resampling: Resampling = Resampling.bilinear,
        ) -> None:
            self.path = Path(path).expanduser().resolve()

            self.canonical_path = (
                Path(canonical_path).expanduser().resolve()
                if canonical_path is not None
                else self.path
            )

            self.source = RasterFile(
                self.path,
                georefs=True,
            )

            self.masked = masked
            self.fill = fill
            self.resampling = resampling

            self._source_ds: DatasetReader | None = None
            self._canonical_ds: DatasetReader | None = None
            self._vrt: WarpedVRT | None = None
            self._ds: DatasetReader | WarpedVRT | None = None


    def __enter__(self) -> "RasterioWindowReader":
        self._source_ds = rasterio.open(self.path)

        if self.canonical_path == self.path:
            self._canonical_ds = self._source_ds
        else:
            self._canonical_ds = rasterio.open(
                self.canonical_path
            )

        if self._same_grid(
            self._source_ds,
            self._canonical_ds,
        ):
            self._ds = self._source_ds
            return self

        vrt_options: dict[str, object] = {
            "crs": self._canonical_ds.crs,
            "transform": self._canonical_ds.transform,
            "width": self._canonical_ds.width,
            "height": self._canonical_ds.height,
            "nodata": self.fill,
            "resampling": self.resampling,
        }

        if self._source_ds.nodata is not None:
            vrt_options["src_nodata"] = (
                self._source_ds.nodata
            )

        self._vrt = WarpedVRT(
            self._source_ds,
            **vrt_options,
        )

        self._ds = self._vrt
        return self


    def __exit__(self, exc_type, exc, tb) -> None:
        if self._vrt is not None:
            self._vrt.close()
            self._vrt = None

        if (
            self._canonical_ds is not None
            and self._canonical_ds is not self._source_ds
        ):
            self._canonical_ds.close()

        if self._source_ds is not None:
            self._source_ds.close()

        self._source_ds = None
        self._canonical_ds = None
        self._ds = None


    @property
    def ds(self) -> DatasetReader | WarpedVRT:
        if self._ds is None:
            raise RuntimeError("dataset is not open")

        return self._ds


    @staticmethod
    def _same_grid(
        source: DatasetReader,
        canonical: DatasetReader,
    ) -> bool:
        return (
            source.crs == canonical.crs
            and source.transform.almost_equals(
                canonical.transform
            )
            and source.width == canonical.width
            and source.height == canonical.height
        )

    @staticmethod
    def to_window(row: PlannedWindow) -> Window:
        return Window(
            col_off=int(row.x),
            row_off=int(row.y),
            width=int(row.w),
            height=int(row.h),
        )

    def validate_row(self, row: PlannedWindow) -> None:
        if row.x < 0 or row.y < 0:
            raise ValueError(f"negative window offset: x={row.x}, y={row.y}")

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

    def geodata(self, row: PlannedWindow) -> TileGeoData:
        win = self.to_window(row)
        crs = self.ds.crs.to_string() if self.ds.crs else ""
        return TileGeoData(
            transform=window_transform(win, self.ds.transform),
            bounds=window_bounds(win, self.ds.transform),
            crs=crs,
        )

    def read_data(
        self,
        row: PlannedWindow,
        *,
        masked: bool,
        fill_value: float | None = None,
        out_dtype: str | np.dtype | None = None,
        bands: Iterable[int] | None = None,
    ) -> TileRead:
        self.validate_row(row)
        indexes = None if bands is None else list(bands)

        arr = self.ds.read(
            indexes=indexes,
            window=self.to_window(row),
            masked=masked,
            out_dtype=out_dtype,
        )

        if arr.ndim == 2:
            arr = arr[np.newaxis, :, :]

        was_masked = bool(np.ma.isMaskedArray(arr))

        if fill_value is not None and np.ma.isMaskedArray(arr):
            arr = np.ma.filled(arr, fill_value)

        return TileRead(
            row=row,
            array=arr,
            masked=was_masked,
            band_count=int(arr.shape[0]),
            dtype=str(arr.dtype),
        )

    def tile_from_row(
        self,
        row: PlannedWindow,
        *,
        masked: bool,
        fill_value: float | int | None,
        out_dtype: str | np.dtype | None = None,
        bands: Iterable[int] | None = None,
    ) -> Tile:
        return Tile(
            plan=row,
            source=self.source,
            read=self.read_data(
                row,
                masked=masked,
                fill_value=fill_value,
                out_dtype=out_dtype,
                bands=bands,
            ),
            geo=self.geodata(row),
        )

    def tiles_from_rows(self, rows: Iterable[PlannedWindow]) -> Iterator[Tile]:
        for row in rows:
            try: 
                yield self.tile_from_row(row, masked = self.masked, fill_value = self.fill)
            except ValueError:
                continue 

