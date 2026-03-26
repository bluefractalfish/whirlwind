"""whirlwind.ingest.config 

    PURPOSE:
        - interpret config for "ingest" pipeling 
        - build typed params 
    BEHAVIOR:
        - merge config layers (global, ingest, ingest mosaic, ingest tiles) with defaults 
        - validate key constraints 
        - resolve onput uris from csv/dir/glob 
        - resolve outpur root dir 
    PUBLIC:
        - parse_ingest_config(input_source, config) -> dict 
        - build_params(input_source, config) -> TParams, QParams 
        


"""
