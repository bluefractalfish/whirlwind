""" 
TSpec describes how windows should be planned.
PlannedWindow stores one planned pixel-space window.
WindowReader reads a PlannedWindow from a raster.
Tile stores the resulting data/geodata/labels.
EncodedTile stores writable bytes + metadata.

"""

from dataclasses import dataclass, asdict 
from typing import Any 

@dataclass(frozen=True) 
class PlannedWindow:
    row_i: int 
    col_i: int 
    x: int 
    y: int 
    w: int 
    h: int

    def record(self) -> dict[str,int]:
        return asdict(self)


    @classmethod 
    def read(cls, data: dict[str, Any]) -> "PlannedWindow":
        return cls( 
                   row_i = int(data["row_i"]),
                   col_i = int(data["col_i"]),
                   x  = int(data["x"]),
                   y  = int(data["y"]),
                   w  = int(data["w"]),
                   h  = int(data["h"])
                )
