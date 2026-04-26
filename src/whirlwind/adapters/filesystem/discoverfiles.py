"""whirlwind.adapters.filesystem.discoverfiles

PUBLIC 
-------- 
DiscoverFiles(path: str | Path)
    contains 
    -------- 
    path: Path 
    uri: str 

    methods 
    ----------
    - discover(options: Tuple[str,...]) -> Iterator[FileRef]
    - is_empty(options: Tuple[str,...]) -> bool 

"""


from dataclasses import dataclass 
from pathlib import Path 
from typing import Iterator, Tuple 

from whirlwind.domain.filesystem.files import FileRef

@dataclass 
class DiscoverFiles: 
    """ 

    DiscoverFiles(path: str | Path)
        contains 
        -------- 
        path: Path 
        uri: str 

        methods 
        ----------
        - discover(options: Tuple[str,...]) -> Iterator[FileRef]
        - is_empty(options: Tuple[str,...]) -> bool 

    """
    path: Path 
    uri: str 

    def   __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.uri = self.path.as_uri()
    
    def discover(self, options: Tuple[str,...]) -> Iterator[FileRef]:
        if self.path.is_dir():
            for f in self.path.rglob("*"):
                if f.is_file() and f.suffix.lower() in options:
                    yield FileRef(f)

    def is_empty(self, options: Tuple[str, ...]) -> bool:
        if not self.path.is_dir():
            return True
        for f in self.path.rglob("*"):
            if f.is_file() and f.suffix.lower() in options:
                return False 
        return True 

