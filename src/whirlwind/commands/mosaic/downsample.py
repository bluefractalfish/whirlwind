
from typing import List, Dict, Any 
from pathlib import Path 
from whirlwind.ui import face 
#from whirlwind.geo.downsample import downsample_mosaic
#from whirlwind.geo.downsample import DSParams 
from whirlwind.tools.pathfinder import build_path
from whirlwind.io.inputs import iter_uris
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from osgeo import ogr, osr
import subprocess 
from osgeo import gdal 
from whirlwind.tools.ids import gen_uuid_from_str, gen_uuid_from_path
from whirlwind.tools.timer import timed 

from dataclasses import dataclass 
from typing import Optional, Tuple, Union, List, Any, Dict


########################
## COMMAND CLASS HEAD ##
########################

class DownsampleCommand(Command):
    name = "downsample"

    def run(self, tokens: List[str], config: Config) -> int:

        face.info("DOWNSAMPLING")
        face.prog_row("1/4","parsing config...")
        face.print_dictionary(config.parse("mosaic","downsample"))
        

        face.prog_row("2/4","building params...")
        dsp = self.build_params(tokens, config)
        if dsp is None:
            face.error("an error was encountered trying to downsample")
            return 3

        face.prog_row("3/4","running gdal_translate...")
        for uri in dsp.uris:
            downsample_mosaic(Path(uri),dsp)
        
        face.success("[4/4]: downsampling completed")
        return 0

         
    def build_params(self, tokens: List[str], config: Config) -> DSParams | None: 
        global_config = config.parse("global","io")
        ds_config = config.parse("mosaic","downsample") 
        match len(tokens):
            case 0:
                # if no input directory default to mnt/
                default_in = Path(global_config["in_dir"])
                _, self.in_path = build_path(default_in)
                exsts,self.dest_path = build_path(global_config["dest_dir"]) 

            case 1:
                _,self.in_path = build_path(tokens[0])
                exsts,self.dest_path = build_path(global_config["dest_dir"]) 
            case 2:
                _, self.in_path = build_path(tokens[0])
                exsts,self.dest_path = build_path(tokens[1])
            case _: 
                face.error("downsample usage: expects 0,1,2 arguments")
                raise ValueError
        # check if destination already has a downsampled mosaic 
        inputs = list(iter_uris(str(self.in_path)))
        dsp = DSParams(
            uris = inputs, 
            out_dir = self.dest_path if self.dest_path else Path("browse"),
            target_resolution = ds_config["target_resolution"], 
            scale_factor = ds_config["scale_factor"], 
            target_width = ds_config["target_width"], 
            target_height = ds_config["target_height"], 
            resampling =  ds_config["resampling"], 
            dtype = ds_config["dtype"], 
            compression = ds_config["compression"],
            tiled = ds_config["tiled"],
            overview_levels = ds_config["overview_levels"],
            nodata = ds_config["nodata"],
            preserve_bounds = ds_config["preserve_bounds"]
            )
        return dsp 


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


