
"""whirlwind.wrangle.config
    PURPOSE:
        Interpret Whirlwind config for the `wrangle mosaics` pipeline and build typed
        params.
    BEHAVIORS:
        - Merge config layers (global + wrangle.mosaics) with defaults.
        - Validate key constraints (stride, percentile bounds).
        - Resolve input URIs from csv/dir/glob. 
        - Resolve output root directory.  
    PUBLIC: 
        - parse_tiles_cfg(input_source, config) -> dict
        - build_params(input_source, config) -> (TParams, QParams)
        
"""


from __future__ import annotations 
from typing import Any, Dict, Tuple 
from whirlwind.wrangler.params import DSParams 
from whirlwind.io.inputs import iter_uris 
from whirlwind.tools import pathfinder as pf 


DEFAULTS: Dict[str, Any] = {
        "input": None,
        "out": "./artifacts",
        "target_resolution":  None,
        "target_width": None,
        "target_height": None,
        "overview_levels": None,
        "scale_factor": 1,
        "resampling": "bilinear",
        "dtype": "Byte", 
        "compression": "LZW",
        "tiled": True, 
        "nodata": 0, 
        "preserve_bounds": False
}


def parse_config(input_source: str, config: Dict[str, Any]) -> Dict[str, Any]:
    root_global = config.get("global", {})
    wrangle_cfg = config.get("wrangle", {})
    wrangle_global = wrangle_cfg.get("global", {}) if isinstance(wrangle_cfg,dict) else {}
    mosaics_downsample_cfg = wrangle_cfg.get("mosaics",{}) if isinstance(wrangle_cfg, dict) else {}
    
    if not isinstance(root_global, dict): 
        root_global = {}
    if not isinstance(wrangle_global, dict):
        wrangle_global = {} 
    if not isinstance(mosaics_downsample_cfg, dict):
        mosaics_downsample_cfg = {} 
    cfg: Dict[str, Any] = dict(DEFAULTS)
    cfg["input"] = input_source 
    cfg.update(root_global)
    cfg.update(wrangle_global)
    cfg.update(mosaics_downsample_cfg)

    if cfg["input"] is None:
        ValueError("config: wrangle.mosaics requires config value: input")
    if cfg["resampling"] not in {"nearest", "bilinear", "cubic", "average"}:
        ValueError("config: wrangle.mosaics requires valid resampling value")
    # check dtypes, compression, etc 

    return cfg 

def build_params(input_source: str, config: Dict[str, Any]) -> DSParams: 
    cfg = parse_config(input_source, config)
    inputs = list(iter_uris(str(cfg["input"]))) 
    out_dir = pf.get_root_(cfg["out"])
    dsp = DSParams(
        uris = inputs, 
        out_dir = out_dir,
        target_resolution = cfg["target_resolution"], 
        scale_factor = cfg["scale_factor"], 
        target_width = cfg["target_width"], 
        target_height = cfg["target_height"], resampling =  cfg["resampling"], 
        dtype = cfg["dtype"], 
        compression = cfg["compression"],
        tiled = cfg["tiled"],
        overview_levels = cfg["overview_levels"],
        nodata = cfg["nodata"],
        preserve_bounds = cfg["preserve_bounds"]
        )
    return dsp 


