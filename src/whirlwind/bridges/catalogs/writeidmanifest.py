""" 



"""

from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.filesystem.runtree import RunTree 
from whirlwind.interface import face


from dataclasses import dataclass, field 
from pathlib import Path 

@dataclass(frozen=True)
class Request: 
    src_dir: Path 
    run_tree: RunTree 
    manifest_name: str = "manifest.csv"
    file_types: tuple[str,...] = (".tif",".tiff")
    verbose: bool = False 
    exempt: str | list[str] = field(default_factory=lambda: ["artifacts", "junk"]) 
    force: bool = False 
    

@dataclass(frozen=True)
class Result: 
    manifest_path: Path 
    files_written: int 
    skipped: bool 
    verbose: bool 
    data: tuple[list[str], list[list[str]]] | None=None
    code: int = 0 



class IDManifestBridge: 
    """ 
        build a manifest of ids for rasters

    """

    def run(self, request: Request) -> Result: 

        code = 0 
        with face.phase(1,3, "ensuring runtree, finding path..."):
            request.run_tree.ensure()
        
            # get path from tree. usually manifest/manifest.csv
            manifest_path = request.run_tree.get_manifest_path_csv(request.manifest_name)

            manifest = IDManifest(
                    path=manifest_path, 
                    file_types=request.file_types
                    )
        
        # get manifest data as list of columns and rows for printing, null of quiet 
        if request.verbose: 
            cols, rows = manifest.show_dont_write(request.src_dir, request.exempt)
        else:
            cols, rows = [], []
            
        if manifest_path.exists() and not request.force:
            with face.phase(2,3, "notice: manifest exists for this path, request force to overwrite"):
                with face.phase(3,3,"returning without writing"):
                    return Result(
                            manifest_path=manifest_path,
                            files_written=0,
                            skipped=True, 
                            verbose = request.verbose,
                            data = (cols, rows),
                            code=0 
                            )
        
        with face.phase(2,3,"writing manifest..."):
            code = manifest.write_from(request.src_dir, request.exempt) # 0, no error. 1, error 
            if code != 0: 
                with face.phase(3,3,"something went wrong with writing manifest"):
                    return Result(
                            manifest_path=manifest_path, 
                            files_written=0, 
                            skipped=False, 
                            verbose = request.verbose, 
                            data = (cols, rows),
                            code=code 
                        )

        with face.phase(3,3,"building report..."):
            return Result(
                    manifest_path=manifest_path, 
                    files_written=self._count_existing_files(manifest),
                    skipped=False, 
                    verbose = request.verbose, 
                    data = (cols, rows),
                    code=0
                    )

    def _count_existing_files(self, manifest: IDManifest) -> int: 
        try: 
            return sum(1 for _ in manifest.paths())
        except FileNotFoundError: 
            return 0
