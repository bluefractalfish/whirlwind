""" whirlwind.behaviors.downsample 

    operational layer between commands and domain objects 

    PUBLIC 
    ------- 
    DownsampleRequest(
                run_tree: RunTree, 
                spec: DSSpec, 
                overwrite: bool = False, 
                display_range: bool = False 
            )

    DownsampleOperation
        run_one(src_path: Path, 
                out_path: Path, 
                request: DownsampleRequest) -> DownsampleResult  


"""


from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from whirlwind.domain.filesystem.runtree import RunTree
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.domain.filesystem.files import RasterFile
from whirlwind.bridges.specs.downsample import DSSpec
from whirlwind.adapters.geo.downsampler import Downsampler


@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    spec: DSSpec
    manifest_path: Path 
    paths: Iterable[Path]
    overwrite: bool = False
    display_range: bool = False 
    
@dataclass 
class Summary: 
    """ 
        per path summary, used to be Result 
    """
    src_path: Path 
    out_path: Path 
    command: str 
    errors: int 
    
@dataclass(frozen=True)
class Result:
    """ 
    result of downsample operation on list of files 
    """
    manifest_path: Path 
    summaries: tuple[Summary,...]
    code: int

class DownsampleBridge:
    def run(self, request: Request) -> Result:
        summaries: list[Summary] = []
        for p in request.paths: 
            f = RasterFile(p)
            mosaic_id = f.file_id
            branch = MosaicBranch.plant(
                                request.run_tree.root, 
                                mosaic_id)
            out = branch.browse_dir / f"b{mosaic_id}"
            
            

            downsampler = Downsampler.from_paths(
                src_path=p,
                out_path=out,
                spec=request.spec,
            )
            
            code, cmd = downsampler.run(overwrite=request.overwrite, disp_range=request.display_range)
            summaries.append(
                    Summary(
                        src_path=p, 
                        out_path=out, 
                        command=cmd,
                        errors=1 if code != 0 else 1
                        )
                )
        code = 0 if all(summary.errors == 0 for summary in summaries) else 1
        return Result(
                manifest_path=request.manifest_path, 
                summaries=tuple(summaries), 
                code = code, 
                )
 
