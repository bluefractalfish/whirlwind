
from typing import Iterable, Any, Literal 
from dataclasses import dataclass, replace  
from pathlib import Path 

from whirlwind.adapters.io.idmanifest import IDManifest 
from whirlwind.adapters.io.raster_tiler import TileRasterFromPlan  
from whirlwind.adapters.label.classifiers.semantic_triage import SemanticLabelTriage, SemanticClassTriage
from whirlwind.adapters.label.null_labeler import UnaryLabeler
from whirlwind.bridges.specs.tiling import TSpec 
from whirlwind.bridges.specs.semclass import SCSpec
from whirlwind.filesystem.files import RasterFile
from whirlwind.filesystem.runtree import RunTree 
from whirlwind.interface import face 
from whirlwind.adapters.geo.stage_gpkg import resolve_damage_path_ref
from whirlwind.adapters.label.classifiers.damage_review import PODClassifier, DamageReviewLabeler
from whirlwind.bridges.specs.review_route_spec import DRRoutingSpec

LabelerType = Literal["null", "spatial","land_cover_triage","damage_review"]


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
    
    labeler_type: LabelerType
    # for intersection with geometry based labels 
    intersection_geom_name: str | None=None
    use_semantic: bool = True
    # specs for semantic classification 
    device: str = "cpu" 
    model_name: str = "ViT-B-32"
    bands: tuple[int,int,int] = (0,1,2)
    tile_limit: int | None = None
    # for masking, removing empty tiles 
    masked: bool = False
    fill_value: float = 0.0 
    min_content_fraction: float = 0.70
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
        paths = tuple(request.paths)
        total_rasters = len(paths)
        with face.phase(1,5,"locating manifest...", delay=0.5):
            if not request.manifest.exists():
                face.error(f"no manifest found for request")
                face.div()
                face.info("run `discover manifest` or ? for help")
                face.div()
                raise FileNotFoundError 
        
        all_records = tuple(request.manifest.records())
        records_by_path = {
                record.path.expanduser().resolve(): record 
                for record in all_records
            }
        seen_bundles: set[str] = set()

        with face.phase(2,5,"constructing tesselation request..."): pass
        summaries: list[Summary] = []
        n_tiles = 0 
        n_rasters = 0 
        with face.phase(3,5,"building tesselation spec, referencing plan..."): pass 
        with face.progress() as pr:
            t1 = pr.add_task("walking manifest",total=total_rasters)
            t2 = pr.add_task("tiling", total=1)
            for requested_path in paths: 
                pr.advance(t1,1) 

                resolved_path = (
                        Path(requested_path).expanduser().resolve()
                        )
                requested_record = records_by_path.get(
                        resolved_path
                        )
                if requested_record is None: 
                    raise ValueError(
                            "mosaic path not found in manifest"
                            f"{resolved_path}"
                        )
                if not requested_record.bundle_id: 
                    raise ValueError(
                            f"{requested_record.mosaic_id}"
                            "has no spatial bundle associated"
                        )
                bundle_id = requested_record.bundle_id 
                
                if bundle_id in seen_bundles: 
                    continue 
                seen_bundles.add(bundle_id)

                bundle_records = tuple(
                        record 
                        for record in all_records 
                        if record.bundle_id == bundle_id
                    )

                if not bundle_records: 
                    raise ValueError(
                            "spatial bundle has no mosaic records: "
                            f"{bundle_id}"
                        )
                canonical_id = (
                        requested_record.canonical_mosaic_id 
                        or requested_record.canonical_mosaic_id
                    )
                canonical_record = next(
                        (
                            record 
                            for record in bundle_records
                            if record.mosaic_id == canonical_id
                            ), 
                        None, 
                    )
                if canonical_record is None: 
                    raise ValueError(
                            "canonical mosaic is missing: "
                            f"{canonical_id}"
                        )
                p = canonical_record.path 

                pr.update(t2, description=f"building tiler for {RasterFile(p).mosaic_id}")
                
                # confirm tile plan exists 
                try:  
                    if request.labeler_type == "land_cover_triage":
                        semantic_classifier_spec = SCSpec(
                            checkpoint_path=Path("~/.cache/whirlwind/remoteclip/RemoteCLIP-ViT-B-32.pt")
                        )
                        classifier = SemanticClassTriage(semantic_classifier_spec)
                        labeler = SemanticLabelTriage(classifier)

                    elif request.labeler_type == "damage_review":
                        semantic_labeler = None 
                        if request.use_semantic: 
                            semantic_classifier_spec = SCSpec(
                                checkpoint_path=Path("~/.cache/whirlwind/remoteclip/RemoteCLIP-ViT-B-32.pt")
                            )
                            semantic_classifier = SemanticClassTriage(semantic_classifier_spec)
                            semantic_labeler = SemanticLabelTriage(semantic_classifier)
                        branch = request.tree.branchlook(request.manifest, p)
                        ref = resolve_damage_path_ref(branch, request.dpath_name.removesuffix(".gpkg"))

                        classifier = PODClassifier.from_gpkg(
                            master_gpkg_path=ref.gpkg_path,
                            mosaic_path=p,
                            line_layer=ref.line_layer,
                            area_layer=ref.area_layer,
                            spec=DRRoutingSpec(),
                            semantic_labeler=semantic_labeler,
                            metamosaic_id=ref.metamosaic_id,
                        )

                        labeler = DamageReviewLabeler(classifier)

                    else:
                        labeler = UnaryLabeler()

                    tiler = TileRasterFromPlan(
                            p,
                            tree=request.tree, 
                            manifest_name=request.manifest_name, 
                            manifest=request.manifest, 
                            manifest_kind=request.manifest_kind, 
                            plan_name=request.plan_name, 
                            shard_prefix=bundle_id, 
                            shard_size=request.shard_size, 
                            masked=request.masked, 
                            fill_value=request.fill_value, 
                            dry=request.dry, 
                            min_content_fraction=request.min_content_fraction, 
                            zero_is_empty=request.zero_is_empty, 
                            labeler=labeler, 
                            overwrite=request.overwrite, 
                            bundle_records=bundle_records
                            ) 

                except FileNotFoundError as e:
                    face.error(str(e))
                    with face.phase(4,5,"something went wrong. no tileplan was found"): pass 
                    summaries.append(Summary(error=9,code=3))
                    continue
                existing_shard = next(
                        tiler.shard_dir.rglob("*.tar"),
                        None,
                    )
                if existing_shard is not None and not request.overwrite:
                    face.info(
                        "skipping spatial bundle "
                        f"{bundle_id}: shards already exist"
                    )
                    summaries.append(Summary(error=0, code=0))
                    continue

                # get sink code (sc): 1 -> ok, else error 
                sc = tiler.build_sinks()
                if sc != 1: 
                    summaries.append(Summary(error=1,code=sc))
                    continue 
                tiles_to_process = tiler.plan_sink.count()
                pr.update(
                        t2, 
                        description=f"tiling{RasterFile(p).mosaic_id}", 
                        total=tiles_to_process, 
                        completed=0
                        )
                tiler.make_shard_request() 

                # tiling operator is run here 
                tilesummary = tiler.run(tile_limit=request.tile_limit, 
                                        progress=pr, task_id=t2) 

                n_rasters += len(bundle_records)
                n_tiles += tilesummary.n_tiles
                summaries.append(Summary(error=0,
                                         code=tilesummary.code,
                                         n_tiles=n_tiles))
        
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


