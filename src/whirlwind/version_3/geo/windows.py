""" whirlwind.geo.windows 
    
    PURPOSE:
        - raster tiling window planning 
    BEHAVIOR:
        - provide deterministic iteration of raster windows 
            - DEFAULT ROW_MAJOR, BUILD DIAGONAL, etc 
        - computes number of full/partial tiles and bounds for window 
        - keep planning/math separate from ingestion and IO 
    PUBLIC:
        - num_tiles(ds, tile_size, stride) -> int 
        - iterate_windows(ds, tp) -> iterator[(row_i,col_i,Window]
        - window_bounds(ds,win) -> minx, miny, maxx, maxy
"""     
