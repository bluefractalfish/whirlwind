"""whirlwind.manifests.mosaic_metadata_manifest

PURPOSE: provides a wrapper for the creation of multiple levels of mosaic metadata manifests 

BEHAVIOR:
    - given a list of mosaic uris, (retrieved from IDmanifest.get_ids()) 
    - write to an out_path, defaults to RunTree.manifest_dir/metadata.csv | .json
        - write(self) -> Path:
            - gets rows to be printed from self.extract(uri)
            - makes out_path 
            - if file_format = json, does a json dump of rows 
            - else gets flat_rows, fieldnames 
            - writes flat_rows 
        - returns out_path 
    - discover(uri) -> dict[str, Any]
        - checks agains self.mode = "core" | "extended" | "full"
        - if mode = "core" return interfaces.geo.Extracter(uri, "core") 
                  = "extended" "" metadata.Extracter(uri, "extended")
                  = "full"     "" metadata.Extracter(uri, "full")

PUBLIC: 
    - if manifest and tree exists, init instance of manifest with RasterMetadata.init_from_tree(uri: str, mode = "core")
    - call write() to write, gets path in return 
"""


from __future__ import annotations

from whirlwind.manifests.idmanifest import IDManifest
from whirlwind.filetrees.runtree import RunTree, MosaicBranch
from whirlwind.interfaces.geo.metadata import GeoMetadataExtractor 
from whirlwind.filetrees.files import RasterFile  
from whirlwind.io.out import write_dict_csv, read_csv_one_row
from whirlwind.commands.base import Command
from whirlwind.ui import face 
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv
import json 


@dataclass 
class RasterMetadata: 
    """
    stores an instance of 
    <File ref> to mosaic raster,  
    and <RasterMetadata>, which is initted with raster uri and, optionally, mode and name. 
    
    each RasterMetadata will be used to create mosaic instance or visa versa. 
    it serves as an interface layer between the mosaic abstract class and the 
    raster-level-metadata collector driven by RasterMetadata 
    
    RasterMetadataManifest 
            | 
      [RasterMetadata,...]  < 

    """
    f: RasterFile  
    extractor: GeoMetadataExtractor 
    mode: str 

    def __init__(self, path: str|Path, mode: str) -> None:
        self.f = RasterFile(path) 
        self.mode = mode
        self.extractor = GeoMetadataExtractor(path, mode)
    
    def discover(self) -> dict[str, Any]: 
        return self.extractor.discover() 
    
    def write_to_mtree(self, tree: MosaicBranch) -> dict[str, Any]: 
        tree.ensure()
        meta_csv = tree.get_meta_path() / f"{self.mode}-metadata.csv"
        if meta_csv.is_file() and meta_csv.exists():
            return self.read_from_mtree(tree)
        meta = self.discover()
        write_dict_csv(meta_csv, [meta])
        return meta 

    def read_from_mtree(self, branch: MosaicBranch) -> dict[str, str]:
       return read_csv_one_row(branch.get_meta_file_path(f"{self.mode}-metadata.csv"))
       

