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

from whirlwind.domain.filesystem.runtree import RunTree
from whirlwind.bridges.specs.downsample import DSSpec
from whirlwind.adapters.geo.downsampler import Downsampler


@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    spec: DSSpec
    overwrite: bool = False
    display_range: bool = False 
    

@dataclass(frozen=True)
class Result:
    """ 
    result of downsampler 

    PUBLIC 
    ------- 
    contents 
    --------- 
    src_path: Path 
    out_path: Path 
    command: tuple[str,...] (what is sent to gdal.subprocesses)
    code: int 
    """
    src_path: Path
    out_path: Path
    command: str
    code: int

class DownsampleBridge:
    def run(self, src_path: Path, out_path: Path, request: Request) -> Result:
        downsampler = Downsampler.from_paths(
            src_path=src_path,
            out_path=out_path,
            spec=request.spec,
        )
        
        code, cmd = downsampler.run(overwrite=request.overwrite, disp_range=request.display_range)
        result = Result(
                src_path=src_path, 
                out_path=out_path, 
                command=cmd,
                code = code 
                )
 
        return result
