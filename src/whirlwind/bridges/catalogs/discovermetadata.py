
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Iterable


from whirlwind.adapters.geo.metadata_extractor import GeoMetadataExtractor
from whirlwind.adapters.io.csv_rows import read_csv_one_row, write_dict_csv
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.filesystem.runtree import RunTree
from whirlwind.interface import face


MetadataMode = Literal["core", "extended", "full"]

CORE_METADATA_COLUMNS = [
    "mosaic_id",
    "uri",
    "driver",
    "driver_long_name",
    "width",
    "height",
    "count",
    "dtype",
    "dtypes",
    "nodata",
    "crs_wkt",
    "srid",
    "transform",
    "footprint_status",
    "footprint_wgs84",
    "minx_wgs84",
    "miny_wgs84",
    "maxx_wgs84",
    "maxy_wgs84",
    "block_shapes",
    "overview_counts",
    "dataset_tags",
    "image_structure",
    "subdatasets",
]

@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    paths: Iterable[Path]
    manifest: IDManifest
    modes: tuple[MetadataMode, ...] = ("core",)
    file_format: str = "csv"
    force: bool = False


@dataclass(frozen=True)
class Summary:
    mode: str
    aggregate_path: Path
    rasters_seen: int
    rasters_written: int
    rasters_skipped: int
    errors: int


@dataclass(frozen=True)
class Result:
    manifest_path: Path
    summaries: tuple[Summary, ...]
    code: int = 0


class DiscoverMetadataBridge:
    def run(self, request: Request) -> Result:

        with face.phase(1,3,"ensuring runtree, finding manifest..."):
            request.run_tree.ensure()

            manifest = request.manifest

            if not manifest.exists():
                raise FileNotFoundError(
                    f"ID manifest does not exist: {request.manifest.path}. "
                    "write id manifest first."
                )
        

        summaries: list[Summary] = []
        with face.phase(2,3,f"parsing modes: {request.modes}"):
            pass 
        with face.progress() as p:
            t = p.add_task("discovering metadata", total=len(request.modes))
            for mode in request.modes:
                p.advance(t,1)
                summaries.append(self._write_mode(request, mode, p))
        code = 0 if all(summary.errors == 0 for summary in summaries) else 1

        return Result(
            manifest_path=manifest.path,
            summaries=tuple(summaries),
            code=code,
        )

    def _write_mode(
        self,
        request: Request,
        mode: MetadataMode,
        p,
    ) -> Summary:
        rows: list[dict[str, object]] = []

        rasters_seen = 0
        rasters_written = 0
        rasters_skipped = 0
        errors = 0
        
        with p:
            t = p.add_task("walking manifest", total=len(list(request.paths)))
            for raster_path in request.paths:
                rasters_seen += 1

                try:
                    branch = request.run_tree.branchlook(request.manifest, raster_path)

                    per_mosaic_path = branch.metadata_dir / f"{mode}-metadata.csv"

                    if per_mosaic_path.exists() and not request.force:
                        rows.append(dict(read_csv_one_row(per_mosaic_path)))
                        rasters_skipped += 1
                        continue

                    metadata = GeoMetadataExtractor(
                        path=raster_path,
                        mode=mode,
                    ).discover()

                    write_dict_csv(per_mosaic_path, [metadata])
                    rows.append(metadata)
                    rasters_written += 1

                except Exception as exc:
                    errors += 1
                    rows.append(
                        {
                            "path": str(raster_path),
                            "mode": mode,
                            "error": type(exc).__name__,
                            "message": str(exc),
                        }
                    )
                p.advance(t,1)
        aggregate_path = request.run_tree.manifest_dir / f"{mode}-metadata.csv"

        if request.file_format != "csv":
            raise ValueError(f"unsupported metadata format: {request.file_format}")

        fieldnames = CORE_METADATA_COLUMNS if mode == "core" else None
        write_dict_csv(aggregate_path, rows, fieldnames=fieldnames)

        return Summary(
            mode=mode,
            aggregate_path=aggregate_path,
            rasters_seen=rasters_seen,
            rasters_written=rasters_written,
            rasters_skipped=rasters_skipped,
            errors=errors,
        )
