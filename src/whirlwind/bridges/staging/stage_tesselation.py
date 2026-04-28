
from typing import Iterator 
from pathlib import Path 
from dataclasses import dataclass 

from whirlwind.bridges.specs.tiling import TSpec 
from whirlwind.domain.filesystem.runtree import RunTree 
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.domain.filesystem.files import RasterFile
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.io.windowplanio import WindowPlanCSV
from whirlwind.adapters.geo.windowplan import WindowPlanner

@dataclass(frozen=True)
class Request: 
    spec: TSpec 
    tree: RunTree 
    manifest: IDManifest 
    paths: Iterator[Path]
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
        summaries: list[Summary] = []
        rasters_seen = 0 
        for p in request.paths: 
            f = RasterFile(p)
            fid = f.file_id
            branch = MosaicBranch.plant(request.tree.root, fid).ensure()
            out_path = branch.manifest_dir/request.plan_name
            planner = WindowPlanner(p, request.spec) 
            sink = WindowPlanCSV(out_path) 
            written = sink.write(planner.rows(), force=request.force)
            if written == 0: 
                skipped = True 
            skipped = False 
            rasters_seen += 1 
            summaries.append(Summary(
                tiles_written=written, 
                skipped = skipped,
                out_path=out_path
                ) 
            )
        tiles_written = sum(summary.tiles_written for summary in summaries )
        rasters_skipped = sum(1 for s in summaries if s.skipped)
        return Result(
                summaries= tuple(summaries), 
                rasters_seen=rasters_seen, 
                skipped = rasters_skipped, 
                tiles_written = tiles_written,  
                code = 0 if tiles_written != 0 else 1
                )


