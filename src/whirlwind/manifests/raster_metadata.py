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
    - extract(uri) -> dict[str, Any]
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
from whirlwind.tools.formatters import flatten_for_csv, fieldnames 
from whirlwind.filetrees.files import RasterFile  
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
        write_csv(meta_csv, [meta])
        return meta 

    def read_from_mtree(self, tree: MosaicBranch) -> dict[str, Any]:
       return {"see":"other"}
       

@dataclass(frozen=True)
class RasterMetadataWriter(Command):
    """ 

    storage and writing class for list of RasterMetadata 

        an instance of this class grown from a tree takes in an existing manifest 
        (id, uri) for uri a raster   
     
     RasterMetadatamanifest <  
            | 
      [RasterMetadata,...]
            |   | | | ... 
            /    
    RasterMetadata 

    """
    name = "write raster metas"

    # for pulling raster ids 
    manifest: IDManifest
    # for writing metadata format 
    out_tree: RunTree
    file_format: str # csv | json 
    mode: str  # core | extended | full 
    name: str 

    def run(self, tokens: list[str], config: Config) -> int:
        ...


    @classmethod 
    def init_from_tree(cls, manifest: IDManifest, out_tree: RunTree, name: str = "metadata", fmt: str = "csv", 
            mode: str = "core", ) -> "RasterMetadataWriter":
        if not manifest.exists():
            raise ValueError("manifest does not exist")
        # ensure out_tree exists, construct if not 
        out_tree.ensure()
        return cls(manifest=manifest, 
                   out_tree = out_tree, 
                   name=name,
                   file_format=fmt, 
                   mode = mode )

    def write(self) -> Path:
        
        # get RasterFile paths from manifest 
        paths = self.manifest.get_paths() 
 
        # for each path create an instance of RasterMetadata and store them as list 
        mosaic_metadata = [RasterMetadata(p, self.mode) for p in paths]
        
        rows = [] 
        # run discover() for each instance of RasterMetadata  
        with face.progress() as p:
            t = p.add_task(f"discovering {self.mode} metadata", total=len(list(mosaic_metadata)))
            for mm in mosaic_metadata:
                # for each RasterMetadata, get RasterFile uid as mosaic id 
                # use RasterMetadata.write_to_mtree to write metadata to
                #      run_id/mosaic_id/metadata/metadata.csv 

                mosaic_id = mm.f.fid.uid
                meta = mm.write_to_mtree(self.out_tree.plant_mosaic_branch(mosaic_id)) 
                rows.append(meta)
                p.update(t, advance=1)

        # use manifest_dir from out_tree run_tree, this  reason runtree is required  
        out_path = self.out_tree.manifest_dir / f"{self.name}.{self.file_format}"
        
        if self.file_format == "json":
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2, sort_keys=True)
            return out_path

        if self.file_format == "csv":
            return write_csv(out_path, rows)

        raise ValueError(f"unsupported format: {self.file_format}")


def write_csv(path: Path, data: list[dict[str, Any]]) -> Path:
   flat_rows = [flatten_for_csv(d) for d in data]
   columns = fieldnames(flat_rows)
   with path.open("w", newline="", encoding="utf-8") as f:
       w = csv.DictWriter(f, fieldnames=columns)
       w.writeheader()
       for row in flat_rows:
           w.writerow({k: row.get(k, "") for k in columns})
   return path
