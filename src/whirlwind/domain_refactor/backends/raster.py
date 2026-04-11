"""whirlwind.backends.raster 
PURPOSE: RASTERS 
    - owns gdal/rasterio raster inspection 
    - owns window reads 
    - downsample writing 
    - transform/bounds helpers 
"""
from __future__ import annotations

from typing import Iterator

from whirlwind.domain_refactor.geometry.mosaic import MOSAIC
from whirlwind.specs import DSSpec, TSpec 

class RasterBackend:
    def inspect(self, uri: str, mosaic_id: str) -> MOSAIC:
        ...

    def inspect_many(self, uris: Iterator[str], id_fn) -> Iterator[MOSAIC]:
        ...

    def read_window(
        self,
        mosaic: MOSAIC,
        x_off: int,
        y_off: int,
        width: int,
        height: int,
        out_dtype: str = "float32",
        masked: bool = True,
    ):
        ...

    def iter_windows(self, mosaic: MOSAIC, spec: TSpec):
        ...

    def num_tiles(self, mosaic: MOSAIC, tile_size: int, stride: int) -> int:
        ...

    def window_bounds(
        self,
        mosaic: MOSAIC,
        x_off: int,
        y_off: int,
        width: int,
        height: int,
    ) -> tuple[float, float, float, float]:
        ...

    def window_transform(
        self,
        mosaic: MOSAIC,
        x_off: int,
        y_off: int,
        width: int,
        height: int,
    ) -> tuple[float, float, float, float, float, float]:
        ...

    def bounds_wgs84(
        self,
        mosaic: MOSAIC,
        x_off: int,
        y_off: int,
        width: int,
        height: int,
    ) -> dict[str, float]:
        ...

    def downsample(self, mosaic: MOSAIC, out_uri: str, spec: DSSpec, mosaic_id: str) -> MOSAIC:
        ...

    def metadata_record(self, mosaic: MOSAIC) -> dict[str, object]:
        ...
