""" 



"""

from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.domain.filesystem.runtree import RunTree 



from dataclasses import dataclass 
from pathlib import Path 

@dataclass(frozen=True)
class Request: 
    src_dir: Path 
    run_tree: RunTree 
    manifest_name: str = "manifest.csv"
    file_types: tuple[str,...] = (".tif",".tiff")
    force: bool = False 

@dataclass(frozen=True)
class Result: 
    manifest_path: Path 
    files_written: int 
    skipped: bool 
    code: int = 0 


class IDManifestBridge: 
    """ 
        build a manifest of ids for rasters, etc 

    """

    def run(self, request: Request) -> Result: 

        request.run_tree.ensure()
        
        # get path from tree. usually manifest/manifest.csv
        manifest_path = request.run_tree.get_manifest_path_csv(request.manifest_name)
        
        if manifest_path.exists() and not request.force:
            existing = IDManifest(manifest_path,file_types=request.file_types)
            return Result(
                    manifest_path=manifest_path,
                    files_written=self._count_existing_files(existing),
                    skipped=True, 
                    code=0
                    )

        manifest = IDManifest(
                path=manifest_path, 
                file_types=request.file_types
                )
        code = manifest.write_from(request.src_dir)

        if code != 0: 
            return Result(
                    manifest_path=manifest_path, 
                    files_written=0, 
                    skipped=False, 
                    code=code 
                )
        return Result(
                manifest_path=manifest_path, 
                files_written=self._count_existing_files(manifest),
                skipped=False, 
                code=0
                )

    def _count_existing_files(self, manifest: IDManifest) -> int: 
        try: 
            return sum(1 for _ in manifest.paths())
        except FileNotFoundError: 
            return 0
