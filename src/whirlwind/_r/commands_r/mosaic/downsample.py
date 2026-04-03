
from typing import List, Dict, Any 
from pathlib import Path 
from whirlwind.ui import face 
from whirlwind._r.geo_r.downsample import downsample_mosaic
from whirlwind.wrangler.params import DSParams 
from whirlwind.tools.pathfinder import build_path
from whirlwind.io.inputs import iter_uris
from whirlwind._r.commands_r import Command 
from whirlwind._r.config_r import Config 



class DownsampleCommand(Command):
    name = "downsample"

    def run(self, tokens: List[str], config: Config) -> int:

        face.info("DOWNSAMPLING")
        face.prog_row("1/?","parsing config")
        config.table("mosaic","downsample")

        ds_config = config.parse("mosaic","downsample") 

        face.prog_row("2/?","building params")
        dsp = self.build_params(tokens, ds_config)
        
        face.prog_row("3/?","running gdal_translate")
        for uri in dsp.uris:
            downsample_mosaic(Path(uri),dsp)
                
        return 0

         
    def build_params(self, tokens: List[str], config: dict[str,Any]) -> DSParams: 
        match len(tokens):
            case 0:
                # if no input directory default to mnt/
                default_in = Path(config["in_dir"])
                _, self.in_path = build_path(default_in)
                _,self.dest_path = build_path(config["dest_dir"]) 

            case 1:
                _,self.in_path = build_path(tokens[0])
                _,self.dest_path = build_path(config["dest_dir"]) 
            case 2:
                _, self.in_path = build_path(tokens[0])
                _,self.dest_path = build_path(tokens[1])
            case _: 
                face.error("downsample usage: expects 0,1,2 arguments")
                raise ValueError
        inputs = list(iter_uris(str(self.in_path)))
        dsp = DSParams(
            uris = inputs, 
            out_dir = self.dest_path if self.dest_path else Path("browse"),
            target_resolution = config["target_resolution"], 
            scale_factor = config["scale_factor"], 
            target_width = config["target_width"], 
            target_height = config["target_height"], 
            resampling =  config["resampling"], 
            dtype = config["dtype"], 
            compression = config["compression"],
            tiled = config["tiled"],
            overview_levels = config["overview_levels"],
            nodata = config["nodata"],
            preserve_bounds = config["preserve_bounds"]
            )
        return dsp 
