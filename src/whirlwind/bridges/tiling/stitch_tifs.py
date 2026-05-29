"""whirlwind.bridges.tiles.stitch_tifs 

given a directory of tifs, stitch together into a tiff using gdalbuildvrt -> gdal_translate 

"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from whirlwind.adapters.geo.tif_stitcher import TifStitcher 
from whirlwind.filesystem.runtree import RunTree
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.interface import face 

@dataclass(frozen=True)
class Request:
    run_tree: RunTree 
    paths: Iterable[Path]
    manifest: IDManifest 
    out_dir_name: str = "stitched"
    pattern: str = "**/*.tif"
    overwrite: bool = True
    bigtiff: str = "IF_SAFER"
    tiled: bool = True
    compress: str = "DEFLATE"

@dataclass(frozen=True)
class Summary:
    error: int
    message: str = ""

@dataclass(frozen=True)
class Result:
    summaries: tuple[Summary, ...]
    code: int


class StitchTifsBridge:
    def run(self, request: Request) -> Result:
        summaries: list[Summary] = []

        with face.phase(1, 3, "locating tile directories..."):
            branch_paths = [Path(p).expanduser().resolve() for p in request.paths]

        with face.phase(2, 3, "building VRTs and stitched TIFFs..."):
            with face.progress() as pr:
                task = pr.add_task("stitching tile groups", total=len(branch_paths))

                for p in branch_paths:
                    pr.advance(task, 1)

                    branch = request.run_tree.branchlook(request.manifest, p)
                    
                    stitcher = TifStitcher(branch, request)

                    if not branch.tiles_dir.exists() or not branch.tiles_dir.is_dir():
                        summaries.append(
                            Summary(
                                error=1,
                                message="tiles directory does not exist",
                            )
                        )
                        continue
                    code, msg = stitcher.stitch()

                    summaries.append(
                            Summary(
                                error=code, 
                                message=msg
                                )
                            )

        with face.phase(3, 3, "building report"):
            pass

        return Result(
            summaries=tuple(summaries),
            code=0 if all(s.error == 0 for s in summaries) else 1,
        )


