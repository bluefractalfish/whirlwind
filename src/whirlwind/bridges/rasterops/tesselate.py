
from typing import Iterable, Any, Literal 
from dataclasses import dataclass, replace  
from pathlib import Path 

from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.adapters.io.raster_tiler import TileRasterFromPlan  
from whirlwind.adapters.label.binary_label_by_intersection import LabelByIntersection
from whirlwind.adapters.classification.semantic import SemanticLabeler, SemanticClassifier
from whirlwind.adapters.label.null_labeler import UnaryLabeler
from whirlwind.bridges.specs.tiling import TSpec 
from whirlwind.bridges.specs.semclass import SCSpec
from whirlwind.filesystem.files import RasterFile
from whirlwind.filesystem.runtree import RunTree 
from whirlwind.interface import face 




@dataclass(frozen=True)
class Request: 
    spec: TSpec 
    tree: RunTree 
    manifest: IDManifest 
    paths: Iterable[Path] 
    prefix: str
    shard_size: int 
    overwrite: bool 
    dry: bool 
    dpath_name: str 
    plan_name: str 
    manifest_name: str 
    manifest_kind: str 
    intersection_label: bool 
    intersection_geom_name: str | None=None
    classification: bool = False
    bands: tuple[int,int,int] = (0,1,2)
    masked: bool = False 
    fill_value: float = 0.0 
    min_content_fraction: float = 1.0
    keep_empty: bool = False 
    zero_is_empty: bool = True 



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
        total_rasters = sum(1 for _ in request.paths)
        with face.phase(3,5,"building tesselation spec, referencing plan..."): pass 
        with face.progress() as pr:
            t1 = pr.add_task("walking manifest",total=total_rasters)
            t2 = pr.add_task("")
            for p in request.paths: 
                pr.advance(t1,1)
                pr.update(t2, description=f"tiling {RasterFile(p).mosaic_id}")
                
                # confirm tile plan exists 
                try:  
                    if request.intersection_label:
                        labeler = LabelByIntersection.from_gpkg(
                                gpkg_path=request.tree.branchlook(request.manifest, p).browse_dir / request.dpath_name,
                                geometry_name=request.intersection_geom_name or "geom",
                                area_layer=f"{request.intersection_geom_name}_area",
                                line_layer=f"{request.intersection_geom_name}_line",
                                target_crs=None,  # temporary problem: you currently need reader.ds.crs for this
                            ) 
                    elif request.classification: 
                        semantic_classifier_spec = SCSpec(rgb_bands=request.bands)
                        print(semantic_classifier_spec.bucket_mode)
                        classifier = SemanticClassifier(semantic_classifier_spec) 
                        labeler = SemanticLabeler(classifier)
                    else:
                            labeler = UnaryLabeler()

                    tiler = TileRasterFromPlan(
                            p,
                            tree=request.tree, 
                            manifest_name=request.manifest_name, 
                            manifest=request.manifest, 
                            manifest_kind=request.manifest_kind, 
                            plan_name=request.plan_name, 
                            shard_prefix=request.prefix, 
                            shard_size=request.shard_size, 
                            masked=request.masked, 
                            fill_value=request.fill_value, 
                            dry=request.dry, 
                            keep_empty=request.keep_empty,
                            min_content_fraction=request.min_content_fraction, 
                            zero_is_empty=request.zero_is_empty, 
                            labeler=labeler
                            ) 

                except FileNotFoundError:
                    with face.phase(4,5,"no tiling plan found"): pass 
                    summaries.append(Summary(error=1,code=3))
                    continue
                # get sink code (sc): 1 -> ok, else error 
                sc = tiler.build_sinks()
                if sc != 1: 
                    summaries.append(Summary(error=1,code=sc))
                    continue 

                tiler.make_shard_request()
                tilesummary = tiler.run() 

                n_rasters += 1
                n_tiles += tilesummary.n_tiles
                summaries.append(Summary(error=0,
                                         code=tilesummary.code,
                                         n_tiles=n_tiles))
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


