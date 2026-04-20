from typing import Any 

INGEST_GRID: dict[str, Any] = {

                  "shard_size": [512],
                  "shard_prefix": ["experiment"],
                  "tile_size": [256,512,],
                  "stride": [256],
                  "drop_partial": [True],
                  "dtype": ["uint16","uint8","float32"],
                  "scale": ["percentile", "minmax","none"],
                  "p_low": [5.0, 2.0],
                  "p_high": [95.0, 98.0],
                  "per_band": [True, False],
                  "stats": ["sample","compute"],
                  "num_samples": [2048],
}
 
