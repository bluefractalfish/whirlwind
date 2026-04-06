
from typing import List, Dict, Any 
from pathlib import Path 
from dataclasses import dataclass 
from typing import List

from whirlwind.ui import face 
from whirlwind.tools.pathfinder import build_path
from whirlwind.interfaces.geo.downsample import downsample_mosaic
from whirlwind.ports.gdal_ports import DSParams 
from whirlwind.io.inputs import iter_uris
from whirlwind.commands.base import Command 
from whirlwind.config import Config 



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


