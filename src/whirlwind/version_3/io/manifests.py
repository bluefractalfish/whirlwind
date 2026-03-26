"""whirlwind.io.manifests 

    PURPOSE:
        - persist per-tile manifest rows 

    BEHAVIOR:
        - Defines stable ManifestRow schema for shards 
        - provide sink for CSV and Parquet 
    PUBLIC:
        - ManifestRow 
        - ManifestSink protocol 
        - CSVSink, ParquetSink 
    
        

"""
