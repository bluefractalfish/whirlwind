
from dataclasses import dataclass, asdict  
from typing import Optional, Dict, Any, Tuple, Union, List

@dataclass 
class DSParams:
    """downsample params for gdal_translate or rasterio_resample"""
    target_resolution: Optional[Tuple[float, float]] = None 
    scale_factor: Optional[float] = None 
    target_width: Optional[int] = None 
    target_height: Optional[int] = None 
    resampling: str = 'nearest' # nearest, bilinear, cubic, average
    dtype: Optional[str] = None # byte, float32 
    compression: str = 'DEFLATE'# DEFLATE, LZW 
    tiled: bool = True          # create tiled geotiff, faster reads 
    overview_levels: Union[List[int], str] = 'AUTO' 
    nodata: Optional[float] = None 
    preserve_bounds: bool = False # if true preserve original bounds exactly 


    def to_record(self) -> dict[str, object ]:
        return asdict(self)



@dataclass(frozen=True)
class DSSpec:
    out_width: int | None = None
    out_height: int | None = None
    x_res: float | None = None
    y_res: float | None = None
    resampling: str = "nearest"
    output_format: str = "GTiff"
    create_overviews: bool = False

    def to_record(self) -> dict[str, object]:
        return asdict(self)
