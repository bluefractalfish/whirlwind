from whirlwind.imps import * 

INGEST_GRID: dict[str, list[Any]] = { 

        # -------------------------
        # TParams-like options
        # -------------------------
        "tile_size": [256, 512],
        "stride": [256],
        "drop_partial": [True],
        "shard_size": [512],
        "manifest": ["csv"],

        # -------------------------
        # QParams-like options
        # -------------------------
        "dtype": ["uint16", "uint8"],
        "scale": ["percentile"],
        "p_low": [5.0],
        "p_high": [95.0],
        "per_band": [True, False],
        "stats": ["sample"],
        "num_samples": [1024, 2048],
}



