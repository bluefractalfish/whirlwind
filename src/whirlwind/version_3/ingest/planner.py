""" whirlwind.ingest.planner 

    PURPOSE:
        - determine output directory layour for ingested mosaics 

    BEHAVIOR:
        - given output root and mosaic_id compute,create:
            - <out-root>/mosaic_id/shards
            - <out_root>/mosaic_id/manifest 
            - etc 
    PUBLIC:
        - mosaic_dirs(out_root, mosaic_id) -> (shards_dir, manifst_dir)

"""
