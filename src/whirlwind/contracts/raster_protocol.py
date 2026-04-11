from __future__ import annotations 

from typing import Any, Protocol, Sequence, runtime_checkable
from whirlwind.geometry.footprint import FootPrint 
import numpy as np 

WindowLike = Any # replace later with concrete window protocol 

@runtime_checkable 
class Raster(Protocol):
    @property 
    def width(self) -> int:
        """ raster width in pixels (x dim)"""
        ... 
    @property 
    def height(self) -> int:
        """ raster height in pixels (y dim)"""
        ... 
    @property 
    def count(self) -> int:
        """ number of bands """
        ... 
    @property 
    def shape(self) -> tuple[int,int]:
        """raster shape as (height, width)"""
        ...
    @property 
    def dtypes(self) -> Sequence[str]:
        """per band dtypes """
        ... 
    @property
    def crs(self) -> Any:
        """coordinate reference system, if spatial """
        ...
    @property 
    def transform(self) -> Any:
        """ pixel-to-world affine transform, if spatial"""
        ... 
    @property 
    def footprint(self) -> FootPrint:
        """global bounds as minx, miny, maxx, maxy, if spatial"""
        ... 
    def read(
        self,
        indexes: int | Sequence[int] | None = None,
        window: WindowLike | None = None,
        out_dtype: str | np.dtype | None = None,
        masked: bool = False, ) -> np.ndarray:
        """
        Read raster values.

        Returns:
            - if indexes is None: array shaped (bands, rows, cols)
            - if indexes is int: array shaped (rows, cols)
            - if indexes is a sequence: array shaped (len(indexes), rows, cols)
        """
        ...

    def window_bounds(
        self,
        window: WindowLike, ) -> FootPrint:
        """Bounds of a window in raster CRS."""
        ...


