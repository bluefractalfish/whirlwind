from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from whirlwind.filesystem.mosaicbranch import MosaicBranch
from whirlwind.geography.bbox import BBox
from whirlwind.geography.geogroup import GeoRow


@dataclass(frozen=True)
class SpatialBranch:
    """
    A group of mosaics aligned to one canonical grid.

    Directory structure:

        branches/<branch_id>/
            staging/
            manifest/
            metadata/
            labels/
            mosaics/     -----> share location space
                <mosaic_id>/ 
    """

    branch_id: str
    branch_dir: Path
    mosaics_dir: Path
    staging_dir: Path
    manifest_dir: Path
    metadata_dir: Path
    labels_dir: Path

    @classmethod
    def plant_at(
        cls,
        branch_dir: str | Path,
        branch_id: str,
    ) -> "SpatialBranch":
        branch_dir = Path(branch_dir).expanduser().resolve()

        return cls(
            branch_id=branch_id,
            branch_dir=branch_dir,
            mosaics_dir=branch_dir / "mosaics",
            staging_dir=branch_dir / "staging",
            manifest_dir=branch_dir / "manifest",
            metadata_dir=branch_dir / "metadata",
            labels_dir=branch_dir / "labels",
        )

    def ensure(self) -> "SpatialBranch":
        for path in (
            self.branch_dir,
            self.mosaics_dir,
            self.staging_dir,
            self.manifest_dir,
            self.metadata_dir,
            self.labels_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

        return self

    def exists(self) -> bool:
        return self.branch_dir.is_dir()

    def mosaic_branch(
        self,
        mosaic_id: str,
    ) -> MosaicBranch:
        return MosaicBranch.plant_at(
            self.mosaics_dir / mosaic_id,
            mosaic_id,
        )

    def tile_plan_path(
        self,
        name: str = "tile_plan.csv",
    ) -> Path:
        return self.staging_dir / name

    def branch_manifest_path(
        self,
        name: str = "manifest.csv",
    ) -> Path:
        return self.manifest_dir / name


@dataclass(frozen=True)
class SpatialBranchSummary:
    metamosaic_id: str
    branch_id: str
    date: str
    canonical_mosaic_id: str
    member_ids: tuple[str, ...]
    min_canonical_similarity: float
    bbox: BBox

    @property
    def n_mosaics(self) -> int:
        return len(self.member_ids)

    def record(self) -> dict[str, str]:
        return {
            "metamosaic_id": self.metamosaic_id,
            "branch_id": self.branch_id,
            "date": self.date,
            "canonical_mosaic_id": self.canonical_mosaic_id,
            "n_mosaics": str(self.n_mosaics),
            "min_canonical_similarity": (
                f"{self.min_canonical_similarity:.12f}"
            ),
            "members": ";".join(self.member_ids),
            **self.bbox.to_record(),
        }


@dataclass(frozen=True)
class _BranchMember:
    mosaic_id: str
    date: str
    manifest_row: dict[str, str]
    geo_row: GeoRow


class BuildSpatialBranch:
    """
    Group rasters by their relationship to a canonical, largest-extent raster.
    """

    def build(
        self,
        *,
        manifest_rows: list[dict[str, str]],
        geo_rows: list[GeoRow],
        threshold: float,
    ) -> tuple[
        list[SpatialBranchSummary],
        dict[str, SpatialBranchSummary],
    ]:
        if not 0.0 < threshold <= 1.0:
            raise ValueError(
                "spatial branch threshold must be in (0, 1]"
            )

        geo_by_mosaic = {
            row.mosaic_id: row
            for row in geo_rows
        }

        members_by_metamosaic: dict[
            str,
            list[_BranchMember],
        ] = {}

        for manifest_row in manifest_rows:
            mosaic_id = self._mosaic_id(manifest_row)
            metamosaic_id = (
                manifest_row.get("metamosaic_id") or ""
            ).strip()

            geo_row = geo_by_mosaic.get(mosaic_id)

            if not mosaic_id or not metamosaic_id or geo_row is None:
                continue

            date = (
                manifest_row.get("date")
                or geo_row.row.get("date")
                or geo_row.row.get("acquired_at")
                or ""
            ).strip()

            members_by_metamosaic.setdefault(
                metamosaic_id,
                [],
            ).append(
                _BranchMember(
                    mosaic_id=mosaic_id,
                    date=date,
                    manifest_row=dict(manifest_row),
                    geo_row=geo_row,
                )
            )

        summaries: list[SpatialBranchSummary] = []
        assignments: dict[str, SpatialBranchSummary] = {}

        for metamosaic_id, members in sorted(
            members_by_metamosaic.items()
        ):
            clusters = self._canonical_clusters(
                members,
                threshold=threshold,
            )

            for cluster in clusters:
                summary = self._summarize_cluster(
                    metamosaic_id=metamosaic_id,
                    members=cluster,
                )

                summaries.append(summary)

                for member in cluster:
                    assignments[member.mosaic_id] = summary

        summaries.sort(
            key=lambda summary: (
                summary.metamosaic_id,
                summary.branch_id,
            )
        )

        return summaries, assignments

    def enrich_manifest(
        self,
        rows: list[dict[str, str]],
        assignments: Mapping[
            str,
            SpatialBranchSummary,
        ],
    ) -> list[dict[str, str]]:
        enriched_rows: list[dict[str, str]] = []

        for row in rows:
            mosaic_id = self._mosaic_id(row)
            summary = assignments.get(mosaic_id)

            enriched = dict(row)

            if summary is None:
                enriched["branch_id"] = ""
                enriched["canonical_mosaic_id"] = ""
            else:
                enriched["branch_id"] = summary.branch_id
                enriched["canonical_mosaic_id"] = (
                    summary.canonical_mosaic_id
                )

            enriched_rows.append(enriched)

        return enriched_rows

    def _canonical_clusters(
        self,
        members: Iterable[_BranchMember],
        *,
        threshold: float,
    ) -> list[list[_BranchMember]]:
        """
        select the largest remaining raster as an anchor, then attach every
        compatible raster sufficiently covered by that anchor.

        allows:

            large A contains small B
            large A contains small C
            B and C do not overlap

        A, B, and C still belong to the same spatial branch and metamosaic
        """

        remaining = sorted(
            members,
            key=self._canonical_score,
            reverse=True,
        )

        clusters: list[list[_BranchMember]] = []

        while remaining:
            canonical = remaining[0]
            cluster = [canonical]
            unassigned: list[_BranchMember] = []

            for candidate in remaining[1:]:
                if not self._dates_compatible(
                    canonical,
                    candidate,
                ):
                    unassigned.append(candidate)
                    continue

                similarity = (
                    canonical.geo_row.bbox.coverage_similarity(
                        candidate.geo_row.bbox
                    )
                )

                if similarity >= threshold:
                    cluster.append(candidate)
                else:
                    unassigned.append(candidate)

            clusters.append(cluster)
            remaining = unassigned

        return clusters

    def _summarize_cluster(
        self,
        *,
        metamosaic_id: str,
        members: list[_BranchMember],
    ) -> SpatialBranchSummary:
        if not members:
            raise ValueError(
                "cannot summarize an empty spatial branch"
            )

        canonical = max(
            members,
            key=self._canonical_score,
        )

        similarities = [
            canonical.geo_row.bbox.coverage_similarity(
                member.geo_row.bbox
            )
            for member in members
        ]

        date = self._common_date(members)

        return SpatialBranchSummary(
            metamosaic_id=metamosaic_id,
            branch_id=self._make_branch_id(
                metamosaic_id=metamosaic_id,
                date=date,
                canonical=canonical,
            ),
            date=date,
            canonical_mosaic_id=canonical.mosaic_id,
            member_ids=tuple(
                sorted(
                    member.mosaic_id
                    for member in members
                )
            ),
            min_canonical_similarity=min(similarities),
            bbox=BBox.union(
                member.geo_row.bbox
                for member in members
            ),
        )

    @staticmethod
    def _dates_compatible(
        left: _BranchMember,
        right: _BranchMember,
    ) -> bool: 
        """ safety check """
        if left.date and right.date:
            return left.date == right.date

        return True

    @staticmethod
    def _canonical_score(
        member: _BranchMember,
    ) -> tuple[float, int, int, int, int, str]:
        """ prioritize large, full range RGB rasters for canonical reference """
        metadata = member.geo_row.row
        manifest = member.manifest_row

        width = BuildSpatialBranch._as_int(
            metadata.get("width")
        )
        height = BuildSpatialBranch._as_int(
            metadata.get("height")
        )
        band_count = BuildSpatialBranch._as_int(
            metadata.get("count")
            or metadata.get("bands")
        )

        pixel_count = width * height
        footprint_area = member.geo_row.bbox.area

        dtype = (
            metadata.get("dtype")
            or metadata.get("data_type")
            or ""
        ).strip().lower()

        full_range = int(
            dtype not in {
                "byte",
                "uint8",
                "int8",
            }
        )

        variant = (
            manifest.get("variant_id")
            or manifest.get("variant_type")
            or ""
        ).strip().upper()

        variant_priority = {
            "RGB": 100,
            "BGR": 95,
            "PANCHRO": 90,
            "NIR": 85,
            "RED": 84,
            "GREEN": 83,
            "BLUE": 82,
            "NLL": 70,
            "ERIK": 50,
            "ERIK2": 49,
            "NDVI": 40,
            "CHM": 30,
            "DSM": 20,
            "DEM": 20,
            "DTM": 20,
        }.get(variant, 0)

        return (
            footprint_area,
            pixel_count,
            full_range,
            variant_priority,
            band_count,
            member.mosaic_id,
        )

    @staticmethod
    def _common_date(
        members: Iterable[_BranchMember],
    ) -> str:
        dates = sorted(
            {
                member.date
                for member in members
                if member.date
            }
        )

        return dates[0] if len(dates) == 1 else "nodate"

    @staticmethod
    def _make_branch_id(
        *,
        metamosaic_id: str,
        date: str,
        canonical: _BranchMember,
    ) -> str:
        """
        ID uses the canonical footprint, not the median member footprint
        """

        bbox = canonical.geo_row.bbox

        signature = {
            "metamosaic_id": metamosaic_id,
            "date": date or "nodate",
            "minx": round(bbox.minx, 4),
            "miny": round(bbox.miny, 4),
            "maxx": round(bbox.maxx, 4),
            "maxy": round(bbox.maxy, 4),
        }

        payload = json.dumps(
            signature,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        digest = hashlib.blake2b(
            payload,
            digest_size=4,
        ).hexdigest()

        safe_date = "".join(
            character
            for character in (date or "nodate")
            if character.isalnum()
        )

        return f"B{safe_date or 'nodate'}{digest}"

    @staticmethod
    def _mosaic_id(
        row: Mapping[str, str],
    ) -> str:
        return (
            row.get("mosaic_id")
            or row.get("file_id")
            or row.get("id")
            or ""
        ).strip()

    @staticmethod
    def _as_int(value: object) -> int:
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return 0
