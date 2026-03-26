"""whirlwind.ingest.quantize 

    PURPOSE:
        - scaling/quantization routines for tile tensors 
    BEHAVIOR:
        - estemate per band bounds by sampling windows 
        - apply scaling and cast output to dtype 
    PUBLIC:
        - sample_bands(ds, tile_size, stride, qp) -> dict[int, (lo,hi)]
        - quantize_tiler(arr, qp, band_bounds) -> (array, meta) 

"""
