from typing import Iterator 
from pathlib import Path 
from dataclasses import dataclass 

from whirlwind.domain.filesystem.runtree import RunTree 
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.domain.filesystem.files import RasterFile
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.geo.damagepath import PathPlan, DamagePathPlanner


@dataclass 
class Request: 
    tree: RunTree 
    manifest_path: Path
    paths: Iterator[Path]
    overwrite: bool 
    set_defaults: bool 

@dataclass 
class Summary: 
    src_path: Path 
    dest_path: Path 
    error: int 
    skipped: bool 

@dataclass 
class Result: 
    manifest_path: Path 
    summaries: tuple[Summary, ...]
    code: int 



class DamagepathStagingBridge:
    def run(self, request: Request) -> Result: 
        summaries: list[Summary] = []
        for p in request.paths: 
            f = RasterFile(p, georefs=True)
            fid = f.file_id 
            branch = MosaicBranch.plant(request.tree.root, fid)
            plan = PathPlan.from_browse(branch, crs_wkt = f.crs_wkt)
            set_default = request.set_defaults 
            overwrite = request.overwrite 
            code = DamagePathPlanner.stage(plan, 
                                           overwrite=overwrite, 
                                           set_defaults=set_default) 
            summaries.append(
                    Summary(
                        src_path = p, 
                        dest_path = plan.gpkg_path, 
                        error = 1 if code == 1 else 0,
                        skipped = True if code == 2 else False
                        )
                    )
        code = 0 if all(summary.error == 0 for summary in summaries ) else 1
        return Result(
                manifest_path=request.manifest_path,
                summaries = tuple(summaries), 
                code = code 
                )
