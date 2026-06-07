"""whirlwind.bridges.tiles.shards_to_tifs 

takes in a directory of shards and outputs a directory of tifs 


"""
from dataclasses import dataclass
from pathlib import Path
from typing import  Literal, Iterable 

from whirlwind.adapters.io.convert_shards import convert_to_tif, ColorBy 
from whirlwind.filesystem.runtree import RunTree
from whirlwind.filesystem.files import RasterFile
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.interface import face 

ExportMode = Literal["display", "raw"]
DisplayKind = Literal["rgb", "rgba"]


@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    manifest: IDManifest 
    paths: Iterable[Path]
    shard_sub_dir: str | None = None 
    display_bands: tuple[int, int, int] | None=None 
    alpha_band: int = 3 
    grouped: bool = True 
    p_low: float = 2.0 
    p_high: float = 98.0 
    compress: str | None = None 
    pattern: str = "*.tar"
    mode: ExportMode = "display"
    display_kind: DisplayKind = "rgb"
    color_by: ColorBy | None=None 
    distance_max: float | None=None 
    overwrite: bool = False
    stop_on_error: bool = False 
    alpha: float = 0.23
    debug: bool = False

    
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
    tifs_written: int 
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
        with face.phase(1,5,"locating manifest...", delay=0.5):
            if not request.manifest.exists():
                face.error(f"no manifest found for request")
                face.div()
                face.info("run `discover manifest` or ? for help")
                face.div()
                raise FileNotFoundError 

        with face.phase(2,5,"building request..."): pass
        with face.phase(3,5,"building command to translate shards to tifs..."): pass 
        summaries: list[Summary] = []
        shards_seen = 0 
        tifs_written = 0 
        with face.phase(4,5, "exporting shards..."): 
            with face.progress() as pr: 
                t1 = pr.add_task("traversing manifest...", total=request.manifest.length)
                t2 = pr.add_task("translating",total=request.manifest.length)
                for p in request.paths:
                    pr.advance(t1,1)
                    pr.update(t2,description=f"translating tiles from {RasterFile(p).mosaic_id}")
                    branch = request.run_tree.branchlook(request.manifest, p)
                    #find shard_dir if exists. expects somethind like shards/"damage" 
                    if request.shard_sub_dir: 
                        shard_dir = branch.shards_dir / request.shard_sub_dir 
                        out_dir = branch.tiles_dir / f"{request.shard_sub_dir}"
                    else: 
                        shard_dir = branch.shards_dir
                        out_dir = branch.tiles_dir 
                    n_shards = sum(1 for p in shard_dir.rglob(request.pattern) if p.is_file())
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
                                    stop_on_error=request.stop_on_error, 
                                    color_by=request.color_by, 
                                    distance_max=request.distance_max, 
                                    alpha = request.alpha,
                                    debug=request.debug
                                )

                        tifs_written += written
                        summaries.append(Summary(
                            src_path=shard_path, 
                            out_path=tile_out, 
                            tiles_seen=seen, 
                            shards_seen=1, 
                            tiles_written=written, 
                            errors=errors
                            ))
        face.phase(5,5, "building report") 
        return Result(shards_seen=shards_seen,
                      summaries=tuple(summaries), 
                      tifs_written = tifs_written,
                      code = 0 if all(s.errors==0 for s in summaries) else 1
                    )



                            
