"""whirwind.geometry.base 

PURPOSE:
        define protocols for geometry objects inherit 
"""

from dataclasses import dataclass, asdict 
from typing import Protocol, Iterable, Iterator, runtime_checkable, Any, ClassVar, Mapping 
from whirlwind.geometry.footprint import Bounds 

# for anything in georeferenced space
@runtime_checkable
class GeometryProtocol(Protocol):
    id: str
    crs: str 
    footprint: Bounds  

    def record(self) -> dict[str,object]:
        ... 

# for anything mosaiclike 
@runtime_checkable 
class ProtoMosaic(GeometryProtocol, Protocol):
    uri: str 
    width: int 
    height: int 
    band_count: int 
    dtype: str 

# for anything tilelike
@runtime_checkable 
class ProtoTile(GeometryProtocol, Protocol):
    parent_id: str 
    source_uri: str 
    x_off: int 
    y_off: int 
    width: int 
    height: int 

@runtime_checkable
class ProtoRow(Protocol):
    FIELDNAMES: ClassVar[tuple[str, ...]]

    def to_record(self) -> dict[str, Any]:...

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ProtoRow":...

