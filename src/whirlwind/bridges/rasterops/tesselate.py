
from typing import Iterable
from dataclasses import dataclass 
from pathlib import Path 

from whirlwind.adapters.geo.windowread import RasterioWindowReader
from whirlwind.bridges.specs.tiling import TSpec 
from whirlwind.domain.geometry.tiles.tile import EncodedTile, TileEncoder
from whirlwind.domain.filesystem.runtree import RunTree 
from whirlwind.domain.filesystem.mosaicbranch import MosaicBranch
from whirlwind.adapters.io.idmanifest import IDManifest 

from whirlwind.adapters.geo.windowread import RasterioWindowReader
from whirlwind.domain.filesystem.files import RasterFile
from whirlwind.adapters.io.windowplanio import WindowPlanCSV
from whirlwind.adapters.io.shardmanifest import make_sink  
from whirlwind.adapters.io.writeshards import ShardWriter, WriteShardRequest, DamageSplitShardWriter
from whirlwind.adapters.geo.damage_labels import DamageLabeler 

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
    code: int 
    gpkg_path: Path 
    plan_path: Path 

@dataclass(frozen=True)
class Result: 
    n_tiles_written: int 
    n_rasters_seen: int 
    summaries: tuple[Summary,...]
    rasters_skipped: int 
    code: int 

class TesselationBridge:

    def run(self, request: Request) -> Result:
        summaries: list[Summary] = []
        n_tiles = 0 
        n_rasters = 0 
        for p in request.paths:
            # for each requested raster path, create RasterFile, TileEncoder, and sink 
            f = RasterFile(p)
            fid = f.file_id  
            encoder = TileEncoder(src=f) 

            #find the mosaicbranch for this path 
            branch = MosaicBranch.plant(request.tree.root, fid).ensure()
            #find this branches relevant dirs/files: 
            shard_dir = branch.shards_dir
            #find the path for the gpkg and tile_plan if they exist 
            #can only label with gpkg present and manually configured 
            gpkg_path = branch.browse_dir/ request.dpath_name    


            tile_plan_path = branch.staging_dir/request.plan_name
            manifest_path = branch.manifest_dir/request.manifest_name 
           
            # check if gpkg is still staged_path, if so skip with code 7 
            if str(gpkg_path).startswith("staged"):     
                summaries.append(Summary(
                                         plan_path=tile_plan_path, 
                                         gpkg_path=gpkg_path, 
                                         code=7, 
                                         error=1,
                                        ))  

            # create sinks 
            manifest_sink = make_sink(request.manifest_kind, manifest_path)
            plan_sink = WindowPlanCSV(tile_plan_path)

            # get iterable(plannedwindows) from tile_plan.csv
            planned_windows = plan_sink.read()
            
            # create shard request from request configuration and this mosaics shard_dir
            req = WriteShardRequest.from_path(
                    out_path=shard_dir, 
                    prefix=request.prefix, 
                    size=request.shard_size,) 

            # only run labeling if --label or -l flag present. 
            # uses SplitShardWriter to write to damage/nodamage bins 
            if request.label: 
                with DamageSplitShardWriter(req) as writer:
                    with RasterioWindowReader(p) as reader: 
                        if not gpkg_path.exists():
                            summaries.append(Summary(plan_path=tile_plan_path, 
                                                     gpkg_path=gpkg_path, 
                                                     code=7, 
                                                     error=1
                                                     )) 
                            continue 
                        labeler = DamageLabeler.from_gpkg(
                                    gpkg_path=branch.browse_dir/gpkg_path,
                                    area_layer="damage_area",
                                    line_layer="damage_path",
                                    target_crs=reader.ds.crs )
                        
                        for tile in reader.tiles_from_rows(planned_windows): 
                            tile = labeler.label(tile)
                            encoded = encoder.encode(tile)
                            if request.dry:
                                print(encoded.key)
                            if not request.dry:
                                placement = writer.write(encoded)
                                print(placement.key)
                                n_tiles += 1 
                                row = encoded.as_manifest_row(placement.key)
                                manifest_sink.write(row)

            # if no labeling request present, shard normally without referencing labeler 
            # or this tiles label metadata 
            elif not request.label:
                with ShardWriter(req) as writer:
                    with RasterioWindowReader(p) as reader: 
                        for tile in reader.tiles_from_rows(planned_windows): 
                            encoded = encoder.encode(tile)
                            if request.dry:
                                print(encoded.key)
                            if not request.dry:
                                placement = writer.write(encoded)
                                print(placement.key)
                                n_tiles += 1 
                                row = encoded.as_manifest_row(placement.key)
                                manifest_sink.write(row)

            summaries.append(Summary(
                                     plan_path=tile_plan_path, 
                                     gpkg_path=gpkg_path,
                                     code=0, 
                                     error=0
                                    ))  
            n_rasters += 1
        
        skipped = sum(1 for s in summaries if s.code==7)

        return Result(
                n_rasters_seen=n_rasters, 
                n_tiles_written=n_tiles,
                rasters_skipped= skipped, 
                summaries=tuple(summaries), 
                code = 0 if all(s.error==0 for s in summaries) else 1
                )


