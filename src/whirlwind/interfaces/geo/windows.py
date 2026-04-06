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


from __future__ import annotations
from typing import Iterator, Tuple
import rasterio
from rasterio.windows import Window
#from whirlwind.commands.mosaic.cut_tiles import TParams

def num_tiles(ds: rasterio.DatasetReader, tile_size: int, stride: int) -> int:
    tiles_x = max(1, (ds.width - tile_size) // stride + 1)
    tiles_y = max(1, (ds.height - tile_size) // stride + 1)
    return tiles_x * tiles_y

def window_bounds(ds: rasterio.DatasetReader, win: Window) -> tuple[float,float, float, float]:
    return rasterio.windows.bounds(win, ds.transform)

def iter_windows(ds: rasterio.DatasetReader, tp: TParams) -> Iterator[Tuple[int, int, Window]]:
    max_x = ds.width
    max_y = ds.height
    tile_size = tp.tile_size
    stride = tp.stride
    if tp.drop_partial:
        x_stops = range(0, max_x - tile_size + 1, stride)
        y_stops = range(0, max_y - tile_size + 1, stride)
    else:
        x_stops = range(0, max_x, stride)
        y_stops = range(0, max_y, stride)
    for ry, y in enumerate(y_stops):
        for cx, x in enumerate(x_stops):
            w = tile_size if (x + tile_size <= max_x) else (max_x - x)
            h = tile_size if (y + tile_size <= max_y) else (max_y - y)
            if tp.drop_partial and (w != tile_size or h != tile_size):
                continue
            yield ry, cx, Window(x, y, w, h) 
