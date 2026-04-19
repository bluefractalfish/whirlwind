"""
PURPOSE:
    - compute per band quantization bounds
    - get other tileside data


"""

from __future__ import annotations 

from pathlib import Path 
from typing import Any, Dict 
from rich.traceback import install 
from whirlwind.tools.pathfinder import build_path
from whirlwind.io.inputs import iter_uris
from whirlwind.commands.base import Command 
from whirlwind.config import Config 
from dataclasses import dataclass 
from whirlwind.ui import face 

from typing import Optional, Tuple, Union, List, Any, Dict
from whirlwind.io.out import append_jsonl
from whirlwind.lab.ingest_experiment import list_configs 


import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds

from whirlwind.geo.windows import window_bounds
from whirlwind.tools import datamonkeys as dm


########################
## COMMAND CLASS HEAD ##
########################
