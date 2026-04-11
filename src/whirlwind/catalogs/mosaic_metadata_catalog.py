"""whirlwind.catalogs.mosaic_metadata_catalog

PURPOSE: provides a wrapper for the creation of multiple levels of mosaic metadata catalogs 

BEHAVIOR:
    - given a list of mosaic uris, (retrieved from IDCatalog.get_ids()) 
    - write to an out_path, defaults to RunTree.catalog_dir/metadata.csv | .json
        - write(self) -> Path:
            - gets rows to be printed from self.extract(uri)
            - makes out_path 
            - if file_format = json, does a json dump of rows 
            - else gets flat_rows, fieldnames 
            - writes flat_rows 
        - returns out_path 
    - extract(uri) -> dict[str, Any]
        - checks agains self.mode = "core" | "extended" | "full"
        - if mode = "core" return interfaces.geo.Extracter(uri, "core") 
                  = "extended" "" metadata.Extracter(uri, "extended")
                  = "full"     "" metadata.Extracter(uri, "full")

"""


from __future__ import annotations

from whirlwind.catalogs.idcatalog import IDCatalog
from whirlwind.filesystem.runtree import RunTree 
from whirlwind.interfaces.geo.metadata import Extracter 
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv

@dataclass(frozen=True)
class MosaicMetadata:
    catalog: IDCatalog
    out_tree: RunTree
    file_format: str = "csv" # csv | json 
    mode: str = "core" # core | extended | full 
    

    @classmethod 
    def init_from_tree(cls, catalog: IDCatalog, out_tree: RunTree, fmt: str = "csv", mode: str = "core") -> "MosaicMetadata":
        if not catalog.exists():
            raise ValueError("catalog does not exist")
        # ensure out_tree exists, construct if not 
        out_tree.ensure()

        return cls(catalog=catalog, 
                   out_tree = out_tree, 
                   file_format=fmt, 
                   mode = mode )

    def write(self) -> Path:
        uris = self.catalog.get_uris() 

        rows = [self.extract(uri) for uri in uris]
        
        out_path = self.out_tree.catalog_dir / f"metadata.{self.file_format}"
        
        if self.file_format == "json":
            with out_path.open("w", encoding="utf-8") as f:
                        json.dump(rows, f, ensure_ascii=False, indent=2, sort_keys=True)
                    return out_path

        if self.file_format == "csv":
            flat_rows = [self._flatten_for_csv(row) for row in rows]
            fieldnames = self._fieldnames(flat_rows)
            with out_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for row in flat_rows:
                    w.writerow({k: row.get(k, "") for k in fieldnames})
            return out_path

        raise ValueError(f"unsupported format: {self.file_format}")
    
    def extract(self) -> dict[str, Any]:
        try: 
            if self.mode == "core":
                return CoreMetadata.extract(uri)


