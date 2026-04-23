
"""whirlwind.geo.downsample 
    PURPOSE:
        - holds logic for downsampling mosaics 
    BEHAVIOR:
        - using DSParams to hold user configuration, downsample using a subprocess 
        `gdal_translate` command or uses the gdal api to return downsampled geotiff with 
        preserved geodata 

"""
from osgeo import ogr, osr
import subprocess 
from osgeo import gdal 
from pathlib import Path 
from whirlwind.specs.downsample import DSSpec 

from dataclasses import dataclass 
from typing import Optional, Tuple, Union, List, Any, Dict


@dataclass 
class Downsampler:
    def __init__(self, src_path: str | Path, out_path: str | Path, spec: DSSpec) -> None: 
        self.src_path = Path(src_path).expanduser().resolve()
        self.out_path = Path(out_path).expanduser().resolve() 
        self.spec = spec 

    def run(self) -> Path: 
        cmd =  build_gdal_subprocess(self.src_path, self.out_path, self.spec) 
        subprocess.run(cmd, check=True)
        return self.out_path 


def build_gdal_subprocess(source_path: Path, out_path: Path, params: DSSpec) -> List[Path | str]:

    cmd = ["gdal_translate","-q","-of", "GTiff"]
    if params.dtype:
        cmd += ["-ot",params.dtype]
    if params.target_resolution:
        xres, yres = params.target_resolution 
        cmd += ["-tr",str(xres),str(yres)]
    elif params.scale_factor: 
        pct = int(params.scale_factor * 100)
        cmd += ["-outsize", f"{pct}%",f"{pct}%"]
    elif params.target_width or params.target_height:
        width = str(params.target_width or 0)
        height = str(params.target_height or 0)
        cmd += ["-outsize", width, height]

    if params.resampling:
        cmd += ["-r", params.resampling] 
    
    if params.nodata is not None:
        cmd += ["-a_nodata", str(params.nodata)]

    co_opts = []

    if params.compression:
        co_opts.append(f"COMPRESS={params.compression}")
    if params.tiled:
        co_opts.append("TILED=YES")
    for co in co_opts:
        cmd += ["-co",co]
    cmd += ["--config","GDAL_TRANSLATE_COPY_SRC_MDD", "YES"]


    cmd += [source_path, out_path]
    
    return cmd



