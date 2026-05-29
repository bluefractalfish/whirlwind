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

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.filesystem.runtree import RunTree
from whirlwind.filesystem.files import RasterFile
from whirlwind.bridges.specs.downsample import DSSpec
from whirlwind.adapters.geo.downsampler import Downsampler

from whirlwind.interface import face 

@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    spec: DSSpec
    manifest: IDManifest
    paths: Iterable[Path]
    overwrite: bool = False
    display_range: bool = True 
    
@dataclass 
class Summary: 
    """ 
        per path summary, used to be Result 
    """
    src_path: Path 
    out_path: Path 
    command: str 
    exists: bool 
    errors: int 
    
@dataclass(frozen=True)
class Result:
    """ 
    result of downsample operation on list of files 
    """
    manifest_path: Path
    summaries: tuple[Summary,...]
    downsampled: int 
    rasters_seen: int 
    exists: int
    code: int

class DownsampleBridge:
    def run(self, request: Request) -> Result:
        with face.phase(1,4,"building downsample request..."): pass 

        summaries: list[Summary] = []
        rasters_seen = 0 
        downsampled = 0 

        with face.phase(2,4, "finding manifest, looking for raster paths..."): pass 
        
        with face.phase(3,4,"downsampling requested rasters..."):
            with face.progress() as pr: 
                length = request.manifest.length
                t1 = pr.add_task("iterating mosaics",total=length)
                t2 = pr.add_task("downsampling", total=length)
                for p in request.paths: 
                    rasters_seen += 1
                    exists = False 

                    pr.advance(t1,1)

                    f = RasterFile(p)
                    mosaic_id = f.mosaic_id

                    branch = request.run_tree.branchlook(request.manifest, p)

                    out = branch.browse_dir / f"b{mosaic_id}"
                    
                    downsampler = Downsampler.from_paths(
                        src_path=p,
                        out_path=out,
                        spec=request.spec,
                    )
                   
                    pr.update(t2,description=f"downsampling {mosaic_id}")
                    try:
                        code, cmd = downsampler.run(overwrite=request.overwrite, disp_range=request.display_range)
                    except FileExistsError:
                        exists = True
                        code = 1 
                        cmd = "already exists"
                        summaries.append(
                                Summary(
                                    src_path=p, 
                                    out_path=out, 
                                    command=cmd,
                                    exists=exists, 
                                    errors=1
                                    )
                            )
                        continue 
                    downsampled += 1
                    summaries.append(
                            Summary(
                                src_path=p, 
                                out_path=out, 
                                command=cmd,
                                exists=exists, 
                                errors=1 if code != 0 else 0
                                )
                        )
                    pr.advance(t2,1)

        with face.phase(3,3,"building report", delay=1): pass 

        code = 0 if all(summary.errors == 0 for summary in summaries) else 1
        already_exists = sum(1 for s in summaries if s.exists)
        return Result(
                manifest_path=request.manifest.path, 
                summaries=tuple(summaries), 
                rasters_seen=rasters_seen,
                downsampled=downsampled,
                exists=already_exists,
                code = code, 
                )
 
