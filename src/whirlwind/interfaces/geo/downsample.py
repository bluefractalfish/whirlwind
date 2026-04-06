
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
from whirlwind.ui import face
from whirlwind.tools.ids import gen_uuid_from_str, gen_uuid_from_path
from whirlwind.tools.timer import timed 
from whirlwind.tools.pathfinder import build_path

from dataclasses import dataclass 
from typing import Optional, Tuple, Union, List, Any, Dict

        
################
## CORE LOGIC ##
################

def downsample_mosaic(source_path: Path,  params: DSParams, subproc: bool=True) -> Path | None:
    
    exists, dest_dir = downsample_dir(str(source_path), params.out_dir)
    if dest_dir is None:
        face.error("an error was encountered constructing path")
        return
    out_path = dest_dir / f"browse-{gen_uuid_from_path(source_path)}"
    if exists == 1:
        face.print(f"browser ready mosaic already exists at {out_path}")
        do = input("    downsample anyway? (y/n)")
        if do == "y":
            face.print(f"overwritting {out_path}...")
            cmd =  build_gdal_subprocess(source_path, out_path, params) 
        else:
            return

    cmd =  build_gdal_subprocess(source_path, out_path, params) 

    face.print("downsampling...")
    subprocess.run(cmd, check=True)
    face.process(str(source_path),"gdal_translate",f"{out_path.name}\n")

    ## change names of PATHSS
    return Path(params.out_dir) / f"{gen_uuid_from_str(str(source_path))}"

def build_gdal_subprocess(source_path: Path, out_path: Path, params: DSParams) -> List[Path | str]:

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


######################
## SPECIALIZED HELP ##
######################

def downsample_dir(source: str, out_path: Path) -> tuple[int,Path|None]: 

    dest = out_path / f"{gen_uuid_from_str(source)}" 
    exists, final_destination = build_path(dest)
    return exists, final_destination

