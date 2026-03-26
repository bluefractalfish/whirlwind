"""whirlwind.ingest.runner 

    PURPOSE:
        - orchestrates multimosaic tiling logic 

    BEHAVIOR:
        - for each input mosaic (uri):
            - open dataset (rasterio)
            
            - sample band bounds if given 
            - iterate windows deterministaclly 
            - cut tile payload 
            - write into shard tars 
            - write manifest rows 
        - provide experiment/performance metrics if requested 
    PUBLIC:
        - MosaicIngestRunner(run, run_experiment) 
        - tesselate(tokwns, config, log) -> int 
"""
