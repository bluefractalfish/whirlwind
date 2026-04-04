""" whirlwind.config.defaults 

    PURPOSE: 
        - centeral location for configuration defaults 

    BEHAVIOURS: 
        - provide a predictable baseline config dict so downstream 
        code can assume top-level sections always exist 

    PUBLIC: 
        - DEFAULT_CONFIG 
        - DEF_CON

"""

from __future__ import annotations 

from typing import Any, Dict 


DEFAULT_CONFIG: Dict[str, Any] = { 
                                  "global": {
                                      "version": "",
                                      "log": "./artifacts/logs",
                                    },
                                  "ingest": {
                                      "global": {},
                                      "tiles": {},
                  }, 
                                  "inspect": {},
                                  "experiments": {},
}

DEF_CON: Dict[str, Any] = {
        "global": {
            "version": "0",
            "in_dir": "./mnt",
            "dest_dir": "./artifacts", 
            "log_dir": "./artifacts/log/"
            },
        "catalog": {
            "build": {
                "dest_dir": "./artifacts/metadata/",
                "file_name": "catalog.csv",
                      },
            "stats": {
                "dest_dir": "./artifacts/metadata/",
                "file_name": "metadata.csv",
                      },
            "validate": {},
            },
        "mosaic" : {
            "info": {},
            "footprint": {},
            "validate": {},
            "downsample": {                
                "out": "./artifacts/browse/",
                "target_resolution":  None,
                "target_width": None,
                "target_height": None,
                "overview_levels": None,
                "scale_factor": 0.25,
                "resampling": "bilinear",
                "dtype": "Byte", 
                "compression": "LZW",
                "tiled": True, 
                "nodata": 0, 
                "preserve_bounds": False
                },
            },

        "tile": {
            "cut": {
                "dest_dir": "./artifacts/tiles/",
                "tile_size": 512,
                "stride": None,
                "drop_partial": True,
                "shard_size": 2048,
                "shard_prefix": "tiles",
                "manifest": "csv",
                "dtype": "float32",
                "scale": "none",
                "p_low": 5.0,
                "p_high": 95.0,
                "per_band": True,
                "stats": "sample",
                "num_samples": 1048,                
            },
            "label": {},
            "stats": {},
            "verify": {},
            },
        "label": {
            "init": {},
            "validate": {},
            },
        "pipeline": {
            "init": {},
            "build": {},
            },
} 
                                                
