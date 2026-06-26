
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable
from dataclasses import dataclass

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.adapters.geo.stage_gpkg import (
    PathPlan,
    MetamosaicPathPlan,
    GeomPathPlanner,
)
from whirlwind.domain.mosaic import MosaicRecord
from whirlwind.filesystem.runtree import RunTree
from whirlwind.filesystem.files import RasterFile
from whirlwind.interface import face

def _selected_records(
    *,
    manifest: IDManifest,
    paths: Iterable[Path],
) -> list[MosaicRecord]:
    selected = {
        Path(p).expanduser().resolve()
        for p in paths
    }

    out: list[MosaicRecord] = []

    for record in manifest.records():
        if record.path.expanduser().resolve() in selected:
            out.append(record)

    return out


def _records_by_scope(
    records: Iterable[MosaicRecord],
) -> dict[str, list[MosaicRecord]]:
    """
    Group records by metamosaic_id.

    Records without metamosaic_id fall back to one scope per mosaic.
    """
    groups: dict[str, list[MosaicRecord]] = defaultdict(list)

    for record in records:
        scope = record.metamosaic_id or f"mosaic:{record.mosaic_id}"
        groups[scope].append(record)

    return dict(groups)


def _write_mosaic_damage_ref(
    *,
    tree: RunTree,
    manifest: IDManifest,
    record: MosaicRecord,
    gpkg_path: Path,
    metadata_path: Path,
    name: str,
    line_layer: str,
    area_layer: str,
) -> Path:
    branch = tree.branch_for(record).ensure()

    ref_path = branch.staging_dir / f"{name}_ref.json"

    payload = {
        "scope": "metamosaic" if record.metamosaic_id else "mosaic",
        "metamosaic_id": record.metamosaic_id,
        "mosaic_id": record.mosaic_id,
        "gpkg_path": str(gpkg_path),
        "metadata_path": str(metadata_path),
        "line_layer": line_layer,
        "area_layer": area_layer,
        "staged_by": "stage_gpkgs",
    }

    with ref_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return ref_path

@dataclass 
class Request: 
    tree: RunTree 
    manifest: IDManifest 
    paths: Iterable[Path]
    overwrite: bool 
    set_defaults: bool 
    name: str = "geom"

@dataclass 
class Summary: 
    src_path: Path 
    dest_path: Path 
    error: int 
    skipped: bool 

@dataclass 
class Result: 
    manifest_path: Path 
    summaries: tuple[Summary, ...]
    skipped: int 
    rasters_seen: int 
    code: int 


class GpkgStagingBridge:
    def run(self, request: Request) -> Result:
        with face.phase(1, 3, "building stage request..."):
            pass

        selected_records = _selected_records(
            manifest=request.manifest,
            paths=request.paths,
        )

        groups = _records_by_scope(selected_records)

        summaries: list[Summary] = []
        rasters_seen = len(selected_records)

        with face.phase(2, 3, "creating staged geopackages..."):
            pass

        with face.progress() as pr:
            t = pr.add_task("planning gpkg paths...", total=len(groups))
            t2 = pr.add_task("writing empty gpkg layers...", total=2 * len(groups))

            for scope, records in groups.items():
                pr.advance(t, 1)

                first = records[0]
                first_raster = RasterFile(first.path, georefs=True)

                if first.metamosaic_id:
                    plan = MetamosaicPathPlan.from_metamosaic(
                        tree=request.tree,
                        metamosaic_id=first.metamosaic_id,
                        crs_wkt=first_raster.crs_wkt,
                        name=request.name,
                    )
                else:
                    # Fallback: old one-GPKG-per-mosaic behavior for loose mosaics.
                    branch = request.tree.branch_for(first).ensure()
                    plan = PathPlan.from_browse(
                        branch,
                        crs_wkt=first_raster.crs_wkt,
                        name=request.name,
                    )

                code = GeomPathPlanner.stage(
                    plan,
                    overwrite=request.overwrite,
                    set_defaults=request.set_defaults,
                )

                # Write a small reference file for each mosaic in this scope.
                # Tesselation should use this instead of searching per-mosaic browse dirs.
                for record in records:
                    _write_mosaic_damage_ref(
                        tree=request.tree,
                        manifest=request.manifest,
                        record=record,
                        gpkg_path=plan.gpkg_path,
                        metadata_path=plan.metadata_path,
                        name=request.name,
                        line_layer=f"{request.name}_line",
                        area_layer=f"{request.name}_area",
                    )

                    summaries.append(
                        Summary(
                            src_path=record.path,
                            dest_path=plan.gpkg_path,
                            error=1 if code == 1 else 0,
                            skipped=True if code == 2 else False,
                        )
                    )

                pr.advance(t2, 2)

        with face.phase(3, 3, "building report", delay=1):
            pass

        skipped = sum(1 for s in summaries if s.skipped)
        code = 0 if all(summary.error == 0 for summary in summaries) else 1
        code = 2 if summaries and all(summary.skipped for summary in summaries) else code

        return Result(
            manifest_path=request.manifest.path,
            summaries=tuple(summaries),
            skipped=skipped,
            rasters_seen=rasters_seen,
            code=code,
        )
