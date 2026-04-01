"""whirlwind.wrangle.params 
    
    PURPOSE:
        - hold downsampling params for gdal, making it easy to 
            specify resolution, scale factor, target size, 
            resampling method, datatype 
    BEHAVIOR:
        - dataclass for:
                - target_resolution 
                - scale_factor 
                - target_width 
                - target_height 
                - resampling 
                - dtype 
                - compression 
                - tiled 
                - overview_levels 
                - nodata 
                - preserve_bounds 
"""

from dataclasses import dataclass 
from typing import Optional, Tuple, Union, List, Any, Dict
from pathlib import Path 

@dataclass 
class DSParams:
    """downsample params for gdal_translate """
    uris: list[str]
    out_dir: Path 
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


    def help(self) -> Dict[str,Any]: 
        help_dict = { 
                
                     "target resolution" : "desired resolution of output",
                     "scale factor" : "scale factor ",
                     "resampling": "choose from nearest, bilinear. cubic, average",
                     "dtype": "byte, float32",
                     "compression": "DEFLATE, LZW",
                     "tiled": "create tiled geotiff",    
                }
        return help_dict 
        


