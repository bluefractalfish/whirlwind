from dataclasses import dataclass 
from pathlib import Path 
from typing import Iterator 

from osgeo import gdal 

#whirlwind imports 
from whirlwind.domain.geometry.tiles.plannedwindow import PlannedWindow 
from whirlwind.bridges.specs.tiling import TSpec 


@dataclass 
class WindowPlanner:
    """ 
        this interface layer between the filesystem and gdal provides 
        window related functions, specifically extracting the 
        window metadata needed to plan a tiling operation, and reading 
        these windows once a plan has been determined 
        
        PUBLIC 
        --------- 
        WindowPlan(path: str | Path, spec: TSpec) -> None 

            contains 
            ---------- 
            path: Path 
            spec: TSpec 
            max_x: int 
            max_y: int 

            methods 
            ---------- 
            rows() -> Iterator(PlannedWindow)

        Example Usage 
        --------------- 

        reader = WindowPlan(p, spec)
            for row in reader.rows():
                planio.append_csv(row)
    """

    def __init__(self, path: str | Path, spec: TSpec) -> None:
        gdal.UseExceptions()
        self.path = Path(path).expanduser().resolve()
        self.spec = spec 


        ## open dataset briefly for height and width, then close 
        ds = gdal.Open(path, gdal.GA_ReadOnly)
        if ds is None:
            raise RuntimeError(...)
        self.max_x = ds.RasterXSize 
        self.max_y = ds.RasterYSize 
        ds = None 
        #######################################################

    
    def rows(self) -> Iterator[PlannedWindow]:
        """ core logic for WindowPlan 
            
            using height and width of input raster and a tiling spec, computes for a raster window the 
            row/column index, the x and y coordinate in pixel space, and the width and height in pixel space 

        """
        max_x = self.max_x
        max_y = self.max_y 
        tile_size = self.spec.tile_size
        stride = self.spec.stride 

        if self.spec.drop_partial:
            x_stops = range(0, max_x - tile_size +1, stride)
            y_stops = range(0, max_y - tile_size +1, stride) 
        else:
            x_stops = range(0, max_x, stride)
            y_stops = range(0, max_y, stride)

        for ri, y in enumerate(y_stops): 
            for ci, x in enumerate(x_stops):
                w = tile_size if (x + tile_size <= max_x) else (max_x - x)
                h = tile_size if (y + tile_size <= max_y) else (max_y - y)
                if self.spec.drop_partial and (w != tile_size or h != tile_size):
                    continue
                yield PlannedWindow(row_i=ri,
                              col_i=ci,
                              x=x,
                              y=y,
                              w=w,
                              h=h )


