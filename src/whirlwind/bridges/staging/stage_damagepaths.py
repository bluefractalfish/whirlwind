from typing import Iterable 
from pathlib import Path 
from dataclasses import dataclass 


from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.geo.damage_path import PathPlan, DamagePathPlanner
from whirlwind.filesystem.runtree import RunTree 
from whirlwind.filesystem.files import RasterFile
from whirlwind.interface import face 

@dataclass 
class Request: 
    tree: RunTree 
    manifest: IDManifest 
    paths: Iterable[Path]
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
    skipped: int 
    rasters_seen: int 
    code: int 



class DamagepathStagingBridge:
    def run(self, request: Request) -> Result: 
        with face.phase(1,3,"building stage request..."): pass 

        summaries: list[Summary] = []
        rasters_seen = 0 

        with face.phase(2,3,"creating geopackages for damagepaths..."): pass 
        with face.progress() as pr: 
            length = request.manifest.length
            t = pr.add_task("planning damagepaths...",total=length)
            t2 = pr.add_task("writing empty gpkg layers...",total=2*length)
            for p in request.paths: 
                rasters_seen += 1
                pr.advance(t,1)

                f = RasterFile(p, georefs=True)

                branch = request.tree.branchlook(request.manifest, p)

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
                pr.advance(t2,2)

        with face.phase(3,3,"building report", delay=1): pass 

        skipped = sum(1 for s in summaries if s.skipped)
        code = 0 if all(summary.error == 0 for summary in summaries ) else 1
        code = 2 if all(summary.skipped for summary in summaries) else code 

        return Result(
                manifest_path=request.manifest.path,
                summaries = tuple(summaries), 
                skipped = skipped, 
                rasters_seen = rasters_seen, 
                code = code 
                )
