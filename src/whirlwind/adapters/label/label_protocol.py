
from typing import Protocol, Any, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from whirlwind.domain.tile import Tile 


class Label(Protocol): 

    """label.bucket controls where tile gets written"""
    bucket: str 

    def metadata(self) -> dict[str, Any]:
        """ returns json safe metadata dictionary """
        ...

@runtime_checkable
class Labeler(Protocol): 
    def label(self, tile: "Tile") -> Label:
        ...
