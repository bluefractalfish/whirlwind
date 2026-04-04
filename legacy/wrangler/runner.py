"""whirlwind.wranglers.runner 

    PURPOSE:
        - contains runners for wrangling commands 

    BEHAVIOR:
        - instantiate runner which wraps all wrangling behaviors. 
        - WrangleMosaicsRunner:
            - instantiate Down sampling params (DSParams) from config and user input 
            - use click to dispatch gdal_translate function 


"""

from __future__ import annotations 

from dataclasses import dataclass 
from pathlib import Path 
from typing import Any, Dict, List, Tuple 

import numpy as np 
import rasterio 
import subprocess 
from osgeo import gdal 
from whirlwind.core.interfaces import LoggerProtocol, NullLogger 
from whirlwind.wrangler.config import build_params 
from whirlwind.wrangler.params import DSParams 
from whirlwind.wrangler.planner import stage_label_gpkg
from whirlwind.wrangler.downsample import downsample_mosaic
from whirlwind.ui import face 


@dataclass 
class WrangleDownsampleRunner: 
    params: DSParams 
    log: LoggerProtocol
    
    @classmethod
    def from_config( 
                    cls,
                    input_source: str,
                    config: Dict[str,Any],
                    log: LoggerProtocol | None=None) -> "WrangleDownsampleRunner":
        base = log or NullLogger()
        dsp = build_params(input_source, config)
        return cls(params=dsp,log=base.child("wrangle downsample"))
    
    def run(self, make_gpkg=False) -> int:
        
        self.params.print_table()
        try:
            for uri in self.params.uris:
                out = downsample_mosaic(uri, self.params)
                if make_gpkg:
                    stage_label_gpkg(out)
                    
        except Exception:
            raise 
        return 0
