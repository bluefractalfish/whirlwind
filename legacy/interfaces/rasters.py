from dataclasses import dataclass 
import numpy as np
import rasterio 
from rasterio import DatasetReader
from rasterio.windows import Window, bounds 
from pathlib import Path 
from typing import Any, Sequence 
from whirlwind.geometry.footprint import FootPrint 


@dataclass 
class RasterioRaster:
    ds: DatasetReader 
    uri: str | None = None 

    @classmethod 
    def open(cls, uri: str | Path, **kwargs: Any)-> "RasterioRaster":
        ds = rasterio.open(uri, "r",**kwargs)
        return cls(ds=ds,uri=str(uri))
    @property 
    def width(self) -> int:
        return self.ds.width 
    @property 
    def height(self) -> int:
        return self.ds.height 
    @property 
    def count(self) -> int:
        return self.ds.count 
    @property 
    def shape(self) -> tuple[int, int]:
        return (self.ds.height, self.ds.width)
    @property 
    def ndim(self) -> int:
        return 3 
    @property 
    def dtypes(self) -> Sequence[str]:
        return self.ds.dtypes 
    @property 
    def crs(self) -> Any:
        return self.ds.crs 
    @property 
    def transform(self) -> Any:
        return self.ds.transform 
    @property 
    def footprint(self) -> FootPrint:
        b = self.ds.bounds 
        return FootPrint(b.left, b.bottom, b.right, b.top)
    @property 
    def read( 
            self, 
            indexes: int | Sequence[int] | None = None, 
            window: Window | None = None, 
            out_dtype: str | np.dtype | None = None, 
            masked: bool = False, ) -> np.ndarray:
            return self.ds.read( 
                indexes=indexes, 
                window=window, 
                out_dtype=out_dtype, 
                masked=masked,
                )
    def window_bounds(self, window: Window) -> FootPrint:
        return bounds(window, self.ds.transform)

    def close(self) -> None:
        self.ds.close()
    def __enter__(self) -> "RasterioRaster":
        return self 
    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

