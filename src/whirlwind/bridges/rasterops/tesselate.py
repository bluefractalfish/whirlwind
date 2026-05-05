
from typing import Iterable
from dataclasses import dataclass 
from pathlib import Path 

from whirlwind.adapters.geo.windowread import RasterioWindowReader
from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.adapters.io.windowplanio import WindowPlanCSV
from whirlwind.adapters.io.shardmanifest import make_sink  
from whirlwind.adapters.io.writeshards import ShardWriter, WriteShardRequest, DamageSplitShardWriter
from whirlwind.adapters.geo.damage_labels import DamageLabeler 
from whirlwind.adapters.geo.windowread import RasterioWindowReader

from whirlwind.bridges.specs.tiling import TSpec 

from whirlwind.domain.geometry.tiles.tile import EncodedTile, TileEncoder
from whirlwind.domain.filesystem.runtree import RunTree 
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.domain.filesystem.files import RasterFile

from whirlwind.face import face 

@dataclass(frozen=True)
class Request: 
    spec: TSpec 
    tree: RunTree 
    manifest: IDManifest 
    paths: Iterable[Path] 
    prefix: str 
    shard_size: int 
    overwrite: bool 
    label: bool 
    dry: bool 
    dpath_name: str 
    plan_name: str 
    manifest_name: str 
    manifest_kind: str 

@dataclass(frozen=True)
class Summary:
    error: int 
    code: int # 3 gpkg doesnt exist/empty, 5 no manifest, 7 no plan, 35 no man no plan, 
    gpkg_path: Path | None=None
    plan_path: Path | None=None
    n_tiles: int=0

@dataclass(frozen=True)
class Result: 
    n_tiles_written: int 
    n_rasters_seen: int 
    summaries: tuple[Summary,...]
    rasters_skipped: int 
    code: int 

class TesselationBridge:

    def run(self, request: Request) -> Result:
        with face.phase(1,5,"locating manifest...", delay=0.5):
            if not request.manifest.exists():
                face.error(f"no manifest found for request")
                face.div()
                face.info("run `discover manifest` or ? for help")
                face.div()
                raise FileNotFoundError 

        with face.phase(2,5,"constructing tesselation request..."): pass
        summaries: list[Summary] = []
        n_tiles = 0 
        n_rasters = 0 
        with face.phase(3,5,"building tesselation spec, referencing plan..."): pass 
        with face.progress() as pr:
            t1 = pr.add_task("walking manifest",total=request.manifest.length)
            t2 = pr.add_task("",total=request.manifest.length)
            for p in request.paths: 
                pr.advance(t1,1)
                pr.update(t2, description=f"tiling {p}")
                
                # confirm tile plan exists 
                try: 
                    tiler = RasterTiler(p,request)
                except FileNotFoundError: 
                    summaries.append(Summary(error=1,code=3))
                    continue
                # get sink code (sc): 1 -> ok, else error 
                sc = tiler.build_sinks()
                if sc != 1: 
                    summaries.append(Summary(error=1,code=sc))
                    continue 

                tiler.make_shard_request()
                # only run labeling if --label or -l flag present. 
                # uses SplitShardWriter to write to damage/nodamage bins 
                if request.label: 
                    summary = tiler.tile_with_labels()

                # if no labeling request present, shard normally without referencing labeler 
                # or this tiles label metadata 
                else:
                    summary = tiler.tile()

                n_rasters += 1
                n_tiles += summary.n_tiles
                summaries.append(summary)
                pr.advance(t2,1)
        
        face.phase(4,4,"assessing summaries...")
        skipped = sum(1 for s in summaries if s.code==7)
        
        face.phase(5,5,"building report",delay=1)
        return Result(
                n_rasters_seen=n_rasters, 
                n_tiles_written=n_tiles,
                rasters_skipped= skipped, 
                summaries=tuple(summaries), 
                code = 0 if all(s.error==0 for s in summaries) else 1
                )


class RasterTiler:
    def __init__(self, p: Path | str, request: Request) -> None: 
        self.p = p 
        self.request = request 
        self.code = 0 
        f = RasterFile(p)
        fid = f.file_id 
        self.encoder = TileEncoder(src=f)
        branch = MosaicBranch.plant(request.tree.root, fid).ensure()
        self.shard_dir = branch.shards_dir
        #find the path for the gpkg and tile_plan if they exist 
        #can only label with gpkg present and manually configured 
        self.gpkg_path = branch.browse_dir/ request.dpath_name    
        self.manifest_path = branch.manifest_dir/request.manifest_name 

        self.tile_plan_path = branch.staging_dir/request.plan_name
        if not self.tile_plan_path.is_file() or not self.tile_plan_path.exists():
            raise FileNotFoundError

    def build_sinks(self) -> int:
        return_code = 1 
        try:  
            self.manifest_sink=make_sink(self.request.manifest_kind, self.manifest_path)
        except ValueError:
            return_code =  5 # cannot make manifest  
        try: 
            self.plan_sink = WindowPlanCSV(self.tile_plan_path)
        except FileNotFoundError: 
            return_code = return_code*7 # tile plan cannot be found or isnt written 
        # return_code == 1 -> no errors, sinks exist 
        # return_code == 5 -> manifest_sink couldnt be made, plan_sink could 
        # return_code == 35 -> neither could be made, skip raster 

        return return_code 
    def make_shard_request(self) -> None: 
        # create shard request from request configuration and this mosaics shard_dir
        self.req = WriteShardRequest.from_path(
                        out_path=self.shard_dir, 
                        prefix=self.request.prefix, 
                        size=self.request.shard_size,) 

    def tile(self) -> Summary:
        planned_windows = self.plan_sink.read() 
        with ShardWriter(self.req) as writer:
            with RasterioWindowReader(self.p) as reader: 
                n_tiles = 0 
                for tile in reader.tiles_from_rows(planned_windows): 
                    encoded = self.encoder.encode(tile)
                    if self.request.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}") 
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.key)
                    self.manifest_sink.write(row)
        
        return Summary(error=0, 
                       code=0, 
                       gpkg_path=self.gpkg_path, 
                       plan_path=self.tile_plan_path, 
                       n_tiles=n_tiles)

    def tile_with_labels(self) -> Summary: 
        planned_windows = self.plan_sink.read() 
        with DamageSplitShardWriter(self.req) as writer:
            with RasterioWindowReader(self.p) as reader: 
                if not self.gpkg_path.exists():
                    return Summary(plan_path=self.tile_plan_path, 
                                             code=3, 
                                             error=1)
                labeler = DamageLabeler.from_gpkg(
                            gpkg_path=self.gpkg_path,
                            area_layer="damage_area",
                            line_layer="damage_path",
                            target_crs=reader.ds.crs )
                n_tiles = 0  
                for tile in reader.tiles_from_rows(planned_windows): 
                    tile = labeler.label(tile)
                    encoded = self.encoder.encode(tile)
                    if self.request.dry:
                        row = encoded.as_manifest_row(f"dry_run_{tile.tile_id}")
                    else:
                        placement = writer.write(encoded)
                        n_tiles += 1 
                        row = encoded.as_manifest_row(placement.key)
                    self.manifest_sink.write(row)

        return Summary(error=0, 
                       code=0, 
                       gpkg_path=self.gpkg_path, 
                       plan_path=self.tile_plan_path, 
                       n_tiles=n_tiles)


