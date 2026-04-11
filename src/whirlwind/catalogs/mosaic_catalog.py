import csv 
from whirlwind.files.files import Directory
from pathlib import Path 
from dataclasses import dataclass 
from typing import Dict, Any, List, Iterator, Tuple

@dataclass 
class MosaicCatalog:
    """ class for writing catalog of mosaics to be used as alternative for walking through directory """
    # where file will be written
    path: Path 
    # what file will be called 
    name: str 
    # what file types will be catalogged 
    file_types: Tuple[str,...] = (".tiff",".tif")

    def __init__(self,path: str|Path, extension: str = "csv") -> None:
        self.path = Path(path).expanduser().resolve()
        #type of file, usually csv 
        self.extension = extension 

    def get_mosaic_ids(self) -> Iterator[str]:
        """returns ids """
        p = self.path 
        if p.is_file() and p.suffix.lower() == ".csv":
            with p.open("r", newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                if "id" not in (r.fieldnames or []):
                    raise ValueError(f"MosaicCatalog missing uri column: {p}")
                for row in r:
                    uri = (row.get("id") or "").strip()
                    if uri:
                        yield uri
            return 

    def write_from(self, src: Path ) -> int:
        """constructs a Directory from path and builds csv of .tif/f uris"""

        # directory containing tiffs 
        mosaic_dir = Directory(src)
        
        if mosaic_dir.is_empty(self.file_types):
            print(f"there are no files like: {self.file_types}")
            return 1
        # list of File objects corresponding to Rasters 
        mosaic_files = mosaic_dir.search_for(self.file_types)

        rows: List[Dict[str,object]] = []
        
        for file in mosaic_files:
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


