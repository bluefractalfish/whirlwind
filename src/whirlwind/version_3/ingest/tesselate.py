"""whirlwind.ingest.tesselate 

    PURPOSE:
        - cur one raster window into a tile tensor + JSON metadata paylow 
        
    BEHAVIOR:
        - read a rasterio window as float32 (always?)
        - apply quantization/scaling if requested 
        - produce metadata 

    PUBLIC:
        - Tile (dataclass)
        - tesselate(tile, ds, qp, tp, band_bounds) -> (npy_btyes, json_bytes, meta_dict)


"""
