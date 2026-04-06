from dataclasses import dataclass 
from typing import Optional, Dict, Any, Tuple, Union, List
from pathlib import Path 
from whirlwind.ui import face

######################
## PARAM CONTAINERS ##
######################

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

    def print_table(self) -> None:
        cols = ["downsampling param","value"]
        rows = [ 
                ["uris",len(self.uris)],
                ["destination",str(self.out_dir)],
                ["target res", str(self.target_resolution if self.target_resolution else "")],
                ["scale factor",str(self.scale_factor if self.scale_factor else "")],
                ["target w", str(self.target_width if self.target_width else "")],
                ["target h", str(self.target_height if self.target_height else "")],
                ["resampling method", self.resampling],
                ["dtype", self.dtype if self.dtype else ""],
                ["compression", self.compression],
                ["tiled", self.tiled],
                ["overview levels", str(self.overview_levels)],
                ["nodata", str(self.nodata if self.nodata else "")],
                ["preserve bounds", self.preserve_bounds]
                ]
        face.table(cols, rows)

