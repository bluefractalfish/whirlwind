"""whirlwind.wrangler.downsample 
    PURPOSE:
        - holds logic for downsampling mosaics 
    BEHAVIOR:
        - using DSParams to hold user configuration, downsample using a subprocess 
        `gdal_translate` command or uses the gdal api to return downsampled geotiff with 
        preserved geodata 

"""
import subprocess 
from osgeo import gdal 
from pathlib import Path 
from whirlwind.wrangler.params import DSParams 
from whirlwind.wrangler.planner import downsample_dir
from whirlwind.ui import face
from whirlwind.tools.ids import gen_uuid_from_str
from whirlwind.tools.timer import timed 

@timed("downsampling")
def downsample_mosaic(source_path: str,  params: DSParams, subproc: bool=True) -> Path:
    return build_gdal_subprocess(source_path, params) 

def build_gdal_subprocess(source_path: str,  params: DSParams) -> Path:

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
    out_path = downsample_dir(source_path, params.out_dir)
    cmd += [source_path, out_path]
    face.process(source_path,"gdal_translate",f"{out_path}")
    subprocess.run(cmd, check=True)

    ## change names of PATHSS
    return Path(params.out_dir) / f"{gen_uuid_from_str(source_path)}"




"""
def run_with_gdal_api(source_path: str, params: DSParams) -> None:
    src_ds = gdal.Open(source_path)
    translate_opts = gdal.TranslateOptions(
            outputSRS=None,
            xRes=params.target_resolution[0] if params.target_resolution else 0.0, 
            yRes=params.target_resolution[1] if params.target_resolution else 0.0, 
            width=params.target_width if params.target_width else 0, 
            height=params.target_height if params.target_height else 0, 
            resampleAlg=params.resampling,
            outputType=params.dtype, 
            creationOptions=co_opts, 
            noData=params.nodata 
        )
"""
