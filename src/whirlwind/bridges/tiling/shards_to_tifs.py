"""whirlwind.bridges.tiles.shards_to_tifs 

takes in a directory of shards and outputs a directory of tifs 


"""
from dataclasses import dataclass
from pathlib import Path
from typing import  Literal, Iterable 

from whirlwind.domain.filesystem.runtree import RunTree
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.domain.filesystem.files import RasterFile
from whirlwind.adapters.io.convertshards import convert_to_tif

ExportMode = Literal["display", "raw"]
DisplayKind = Literal["rgb", "rgba"]


@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    paths: Iterable[Path]
    shard_sub_dir: str
    display_bands: tuple[int, int, int] | None=None 
    alpha_band: int = 3 
    grouped: bool = True 
    p_low: float = 2.0 
    p_high: float = 98.0 
    compress: str | None = None 
    pattern: str = "*.tar"
    mode: ExportMode = "display"
    display_kind: DisplayKind = "rgb"
    overwrite: bool = False
    stop_on_error: bool = False 

    
@dataclass 
class Summary: 
    """ 
        per path summary for each mosaic  
    """
    src_path: Path 
    out_path: Path 
    tiles_seen: int 
    shards_seen: int 
    tiles_written: int 
    errors: int 
    
@dataclass(frozen=True)
class Result:
    """ 
    result of shard export operation on list of files 
    """
    shards_seen: int 
    summaries: tuple[Summary,...]
    code: int


class ExportShardsBridge: 
    def run(self, request: Request) -> Result:

        """
            purpose: mosaic1/shards/shard_dir/abc.npy, abc.json -> tiles/tile_dir/abc.tif 

            for each path in list of paths:
                shard_dir = mosaicbranch(path).shard_dir / "damage" | "shards" | "nodamage"
                out_dir = mosaicbranch(path).tiles_dir / "damage" | "tiles" | "nodamage"
                
                for shard_path in shard_dir: 
                    tiles_seen, tiles_written, errors = convert_to_tif( 
                            shard_path, 
                            out_dir, 
                            mode, 
                            display_kind, 
                            display_bands, 
                            p_low, 
                            p_high, 
                            compress, 
                            stop_on_error 
                    )

        """
        summaries: list[Summary] = []
        shards_seen = 0 
        for p in request.paths:
            print(p)
            f = RasterFile(p)
            fid = f.file_id 
            # find mosaic branch for this path 
            branch = MosaicBranch.plant(request.run_tree.root, fid).ensure()
            #find shard_dir if exists. expects somethind like shards/"damage" 
            shard_dir = branch.shards_dir / request.shard_sub_dir 
            #find tiles_dir 
            out_dir = branch.tiles_dir / f"{request.shard_sub_dir}"
            
            for shard_path in sorted(shard_dir.rglob(request.pattern)): 
                if not shard_path.is_file():
                    continue 
                shards_seen +=1 
                tile_out = out_dir / shard_path.stem if request.grouped else out_dir 
                seen, written, errors = convert_to_tif(
                            shard_path=shard_path, 
                            out_dir=tile_out, 
                            mode=request.mode, 
                            display_kind=request.display_kind, 
                            display_bands=request.display_bands, 
                            alpha_band=request.alpha_band, 
                            p_low=request.p_low, 
                            p_high=request.p_high, 
                            compress=request.compress, 
                            stop_on_error=request.stop_on_error
                        )
                summaries.append(Summary(
                    src_path=shard_path, 
                    out_path=tile_out, 
                    tiles_seen=seen, 
                    shards_seen=1, 
                    tiles_written=written, 
                    errors=errors
                    ))
            
        return Result(shards_seen=shards_seen,
                      summaries=tuple(summaries), 
                      code = 0 if all(s.errors==0 for s in summaries) else 1
                    )



                            
