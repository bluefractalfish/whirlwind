from dataclasses import dataclass 
from pathlib import Path 
from typing import Iterator, Tuple 

from whirlwind.filetrees.files import File, RasterFile

@dataclass 
class Directory: 
    path: Path 
    uri: str 

    def   __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.uri = self.path.as_uri()
    
    def search_for(self, options: Tuple[str,...]) -> Iterator[File]:
        if self.path.is_dir():
            for f in self.path.rglob("*"):
                if f.is_file() and f.suffix.lower() in options:
                    yield File(f)

    def is_empty(self, options: Tuple[str, ...]) -> bool:
        if not self.path.is_dir():
            return True
        for f in self.path.rglob("*"):
            if f.is_file() and f.suffix.lower() in options:
                return False 
        return True 

