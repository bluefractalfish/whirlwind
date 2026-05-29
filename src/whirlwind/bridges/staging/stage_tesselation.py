
from typing import Iterable 
from pathlib import Path 
from dataclasses import dataclass 

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.io.windowplan_io import WindowPlanCSV
from whirlwind.adapters.geo.window_plan import WindowPlanner
from whirlwind.bridges.specs.tiling import TSpec 
from whirlwind.filesystem.runtree import RunTree 
from whirlwind.interface import face 

@dataclass(frozen=True)
class Request: 
    spec: TSpec 
    tree: RunTree 
    manifest: IDManifest 
    paths: Iterable[Path]
    force: bool 
    plan_name: str="tile_plan.csv"

@dataclass(frozen=True)
class Summary: 
    tiles_written: int 
    skipped: bool 
    out_path: Path 

@dataclass(frozen=True)
class Result: 
    summaries: tuple[Summary, ...]
    rasters_seen: int 
    skipped: int 
    tiles_written: int 
    code: int 


class StageTesselationBridge: 
    def run(self, request: Request) -> Result: 

        with face.phase(1,4,"building tile stage request..."): pass 

        summaries: list[Summary] = []
        rasters_seen = 0 

        with face.phase(2,4, "planning tiles per mosaic..."): pass 
        with face.phase(3,4, "ensuring mosaic branches..."): pass 

        with face.progress() as pr:
            t = pr.add_task("walking manifest ", total=request.manifest.length)
            t2 = pr.add_task("planning tiles ", total=request.manifest.length)
            for p in request.paths: 
                pr.advance(t,1)

                skipped = False 
                
                branch = request.tree.branchlook(request.manifest,p)

                out_path = branch.staging_dir/request.plan_name

                planner = WindowPlanner(p, request.spec) 
                sink = WindowPlanCSV(out_path) 
                written = sink.write(planner.rows(), force=request.force)

                if written == 0: 
                    skipped = True 

                rasters_seen += 1 

                summaries.append(Summary(
                    tiles_written=written, 
                    skipped = skipped,
                    out_path=out_path
                    ) 
                )
                pr.advance(t2,1)
        with face.phase(4,4,"building report",delay=1): pass 
        tiles_written = sum(summary.tiles_written for summary in summaries )
        rasters_skipped = sum(1 for s in summaries if s.skipped)

        code = 0 if rasters_seen != rasters_skipped else 2
        return Result(
                summaries= tuple(summaries), 
                rasters_seen=rasters_seen, 
                skipped = rasters_skipped, 
                tiles_written = tiles_written,  
                code = code
                )


