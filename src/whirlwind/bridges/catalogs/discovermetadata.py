
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from whirlwind.adapters.geo.metadata_extractor import GeoMetadataExtractor
from whirlwind.adapters.io.csv_rows import read_csv_one_row, write_dict_csv
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.domain.filesystem.files import RasterFile
from whirlwind.domain.filesystem.runtree import RunTree


MetadataMode = Literal["core", "extended", "full"]


@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    manifest_name: str = "manifest.csv"
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
        request.run_tree.ensure()

        manifest_path = request.run_tree.get_manifest_path_csv(request.manifest_name)
        manifest = IDManifest(manifest_path)

        if not manifest.exists():
            raise FileNotFoundError(
                f"ID manifest does not exist: {manifest_path}. "
                "write id manifest first."
            )

        summaries: list[Summary] = []

        for mode in request.modes:
            summaries.append(self._write_mode(request, manifest, mode))

        code = 0 if all(summary.errors == 0 for summary in summaries) else 1

        return Result(
            manifest_path=manifest_path,
            summaries=tuple(summaries),
            code=code,
        )

    def _write_mode(
        self,
        request: Request,
        manifest: IDManifest,
        mode: MetadataMode,
    ) -> Summary:
        rows: list[dict[str, object]] = []

        rasters_seen = 0
        rasters_written = 0
        rasters_skipped = 0
        errors = 0

        for raster_path in manifest.paths():
            rasters_seen += 1

            try:
                raster = RasterFile(raster_path)
                branch = request.run_tree.plant_mosaic_branch(raster.mid)

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

        aggregate_path = request.run_tree.manifest_dir / f"{mode}-metadata.csv"

        if request.file_format != "csv":
            raise ValueError(f"unsupported metadata format: {request.file_format}")

        write_dict_csv(aggregate_path, rows)

        return Summary(
            mode=mode,
            aggregate_path=aggregate_path,
            rasters_seen=rasters_seen,
            rasters_written=rasters_written,
            rasters_skipped=rasters_skipped,
            errors=errors,
        )
