"""whirlwind.manifests.idmanifest 

PURPOSE: wrapper for writing and reading from/to manifest of file ids/uris

BEHAVIOR: 
    - init from path ( defaults to tif/f file_types and csv writing )
    - holds onto path. 
    - when called write_from, search through src directory and retrieve Files, which 
        - store "id, uri" records 
    - when called get_ids return iterator of file uids (File.FileId.uid)

PUBLIC:
    - IDManifest(path: str | Path, extension: str = "csv", file_types: Tuple[str,...]=(".tif",".tiff"))
    - .write_from(src: Path) -> writes csv at self.path after searching src for file_types 
    - .get_ids -> returns iterator of ids contained in ^
"""


import csv 
from whirlwind.filesystem import Directory
from pathlib import Path 
from dataclasses import dataclass 
from typing import Dict, Any, List, Iterator, Tuple

@dataclass 
class IDManifest:
    """ class for writing manifest of file_types with (id, uris )to be used as alternative for walking through directory """
    # where file will be written
    path: Path 
    # what file types will be manifestged 
    file_types: Tuple[str,...]

    # what file will be called (optional)
    name: str | None = None

    def __init__(self,path: str|Path, extension: str = "csv", file_types: Tuple[str,...]=(".tiff", ".tif")) -> None:
        self.path = Path(path).expanduser().resolve()
        self.file_types = file_types
        #type of file, usually csv 
        self.extension = extension 
    

    def exists(self) -> bool:
        return self.path.exists() and self.path.is_file()

    @classmethod
    def get_manifest(cls, path: str | Path) -> "IDManifest":
        return IDManifest(path) 

    @classmethod 
    def write_now(cls, dest: Path, src: Path, file_types=(".tif",".tiff") ) -> "IDManifest":
        manifest = cls(path=Path(dest), file_types=file_types) 
        manifest.write_from(Path(src))
        return manifest

    def get_ids(self) -> Iterator[str]:
        """returns ids as strings iterator  """
        p = self.path 
        if p.is_file() and p.suffix.lower() == ".csv":
            with p.open("r", newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                if "id" not in (r.fieldnames or []):
                    raise ValueError(f"IDManifest missing id column: {p}")
                for row in r:
                    ids = (row.get("id") or "").strip()
                    if ids:
                        yield ids
            return 

    def get_uris(self) -> Iterator[str]:
        """returns uris as strings iterator """
        p = self.path 
        if p.is_file() and p.suffix.lower() == ".csv":
            with p.open("r", newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                if "uri" not in (r.fieldnames or []):
                    raise ValueError(f"IDManifest missing uri column: {p}")
                for row in r:
                    uri = (row.get("uri") or "").strip()
                    if uri:
                        yield uri

    def get_paths(self) -> Iterator[Path]: 
        """ returns paths as Path iterator """
        p = self.path 
        if p.is_file() and p.suffix.lower() == ".csv":
            with p.open("r", newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                if "path" not in (r.fieldnames or []):
                    raise ValueError(f"IDManifest missing path column: {p}")
                for row in r: 
                    path = Path((row.get("path") or "").strip()) 
                    if path: 
                        yield path 
        
                    

    def write_from(self, src: Path ) -> int:
        """constructs a Directory from path and builds csv of file_type uris"""

        # directory containing tiffs 
        search_dir = Directory(src)
        
        if search_dir.is_empty(self.file_types):
            print(f"there are no files like: {self.file_types}")
            return 1
        # list of File objects of kind <file_type>  
        found_files = search_dir.search_for(self.file_types)

        rows: List[Dict[str,object]] = []
        
        for file in found_files:
            rows.append(file.record)
        
        
        cols = rows[0].keys()

        try: 
            with self.path.open("w", newline="",encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in rows:
                    w.writerow({k: r.get(k,"") for k in cols })
            return 0
        except: 
            return 1


