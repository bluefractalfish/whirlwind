import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from whirlwind.adapters.io.csv_rows import write_dict_csv
from whirlwind.adapters.io.idmanifest import IDManifest

from whirlwind.geography.geogroup import GeoRow, GeoGroup, read_georows

from whirlwind.geography.location import (
        FolderHintLocationResolver, LocationResolver
        )
from whirlwind.filesystem.files import FileID
from whirlwind.filesystem.runtree import RunTree
from whirlwind.domain.mosaic import MosaicRecord
from whirlwind.interface import face


@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    manifest: IDManifest
    metadata_path: Path
    stem: str = "locale"
    metamosaic_manifest_name: str = "metamosaic.csv"
    metamosaic_summary_name: str = "metamosaic_summary.csv"
    root_manifest_name: str = "manifest.csv"
    force: bool = False
    location_resolver: LocationResolver | None = None 

@dataclass(frozen=True)
class Summary:
    metamosaic_id: str
    n_mosaics: int
    site_guess: str 
    minx_wgs84: float
    miny_wgs84: float
    maxx_wgs84: float
    maxy_wgs84: float
    members: tuple[str, ...]

@dataclass(frozen=True)
class Result:
    metamosaic_manifest_path: Path
    root_manifest_path: Path
    metamosaics_written: int
    mosaics_seen: int
    intersections: int
    summaries: tuple[Summary,...]
    code: int = 0


class UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def groups(self) -> list[list[str]]:
        out: dict[str, list[str]] = {}
        for item in self.parent:
            out.setdefault(self.find(item), []).append(item)
        return [sorted(v) for v in out.values()]


class BuildMetamosaicBridge:
    def run(self, request: Request) -> Result:
        with face.phase(1, 4, "loading metadata and manifest from request..."):
            geo_rows = read_georows(request.metadata_path)
            manifest_rows = self._read_manifest_rows(request.manifest.path)

        with face.phase(2, 4, "building footprint intersection graph..."):
            groups, pairs = self._intersect_groups(geo_rows)

        with face.phase(3, 4, "assigning metamosaic ids..."):
            mm_by_mid: dict[str, str] = {}
            geo_groups: list[GeoGroup] = []
            
            resolver = request.location_resolver or FolderHintLocationResolver()
            geo_by_mid = {row.mosaic_id: row for row in geo_rows}

            for member_ids in groups:
                members = [
                        geo_by_mid[mid] 
                        for mid in member_ids 
                        if mid in geo_by_mid 
                    ]
                stem = self._metamosaic_stem(
                        members = members, 
                        requested_stem=request.stem, 
                        resolver=resolver
                        )

                mmid = FileID.metamosaic(member_ids, stem=stem)

                for mid in member_ids:
                    mm_by_mid[mid] = mmid
                
                geo_groups.append(
                        GeoGroup.from_members(
                            group_id=mmid, 
                            members=members, 
                            resolver=resolver,
                            )
                        )

        summaries = self._summary_rows_from_groups(geo_groups)

        with face.phase(4, 4, "writing metamosaic tree and manifests..."):
            enriched_manifest_rows = self._enrich_manifest_rows(
                manifest_rows,
                mm_by_mid,
            )

            root_manifest_path = request.run_tree.get_manifest_path_csv(
                request.root_manifest_name
            )

            write_dict_csv(root_manifest_path, enriched_manifest_rows)

            metamosaic_rows = self._membership_rows(enriched_manifest_rows)
            metamosaic_manifest_path = (
                request.run_tree.manifest_dir / request.metamosaic_manifest_name
            )

            write_dict_csv(metamosaic_manifest_path, metamosaic_rows)

            intersection_path = request.run_tree.manifest_dir / "metamosaic-intersections.csv"
            write_dict_csv(
                intersection_path,
                [
                    {
                        "mosaic_a": a,
                        "mosaic_b": b,
                        "metamosaic_id": mm_by_mid.get(a, ""),
                    }
                    for a, b in pairs
                ],
            )

            metamosaic_summary_path = (
            request.run_tree.manifest_dir / request.metamosaic_summary_name
            )

            write_dict_csv(
            metamosaic_summary_path,
            [group.to_metamosaic_record() for group in geo_groups],
            )

            self._plant_trees(request.run_tree, enriched_manifest_rows)

        return Result(
            metamosaic_manifest_path=metamosaic_manifest_path,
            root_manifest_path=root_manifest_path,
            metamosaics_written=len(set(mm_by_mid.values())),
            summaries=summaries,
            mosaics_seen=len(geo_rows),
            intersections=len(pairs),
            code=0,
        )

    def _read_manifest_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8") as f:
            return [dict(row) for row in csv.DictReader(f)]

    def _intersect_groups(
        self,
        rows: list[GeoRow],
    ) -> tuple[list[list[str]], list[tuple[str, str]]]:
        uf = UnionFind(row.mosaic_id for row in rows)
        pairs: list[tuple[str, str]] = []

        for i, a in enumerate(rows):
            for b in rows[i + 1 :]:
                if a.bbox.intersects(b.bbox):
                    uf.union(a.mosaic_id, b.mosaic_id)
                    pairs.append((a.mosaic_id, b.mosaic_id))

        return uf.groups(), pairs

    def _enrich_manifest_rows(
        self,
        rows: list[dict[str, str]],
        mm_by_mid: dict[str, str],
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []

        for row in rows:
            mid = row.get("mosaic_id") or row.get("file_id") or row.get("id") or ""
            mmid = mm_by_mid.get(mid, "")

            enriched = dict(row)
            enriched["metamosaic_id"] = mmid
            enriched["branch_id"] = FileID.branch(mid)

            out.append(enriched)

        return out

    def _membership_rows(
        self,
        rows: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        return [
            {
                "metamosaic_id": row.get("metamosaic_id", ""),
                "mosaic_id": row.get("mosaic_id", ""),
                "branch_id": row.get("branch_id", ""),
                "path": row.get("path", ""),
                "source_uri": row.get("source_uri", ""),
                "date": row.get("date", ""),
                "variant_id": row.get("variant_id", ""),
                "variant_type": row.get("variant_type", ""),
                "spectral_id": row.get("spectral_id", ""),
            }
            for row in rows
            if row.get("metamosaic_id")
        ]

    def _summary_rows_from_groups(
    self,
    groups: list[GeoGroup],
    ) -> tuple[Summary, ...]:
        summaries: list[Summary] = []

        for group in groups:
            summaries.append(
                Summary(
                    metamosaic_id=group.group_id,
                    n_mosaics=group.n_members,
                    site_guess=group.site_guess,
                    minx_wgs84=group.bbox.minx,
                    miny_wgs84=group.bbox.miny,
                    maxx_wgs84=group.bbox.maxx,
                    maxy_wgs84=group.bbox.maxy,
                    members=group.member_ids,
                )
            )

        return tuple(summaries)



    def _plant_trees(
        self,
        tree: RunTree,
        rows: list[dict[str, str]],
    ) -> None:
        metamosaic_ids = sorted(
            {
                row.get("metamosaic_id", "")
                for row in rows
                if row.get("metamosaic_id")
            }
        )

        for mmid in metamosaic_ids:
            tree.metamosaic_tree(mmid).ensure()

        for row in rows:
            record = MosaicRecord.from_row(row)
            tree.branch_for(record).ensure()



    def _metamosaic_stem(
        self,
        *,
        members: list[GeoRow],
        requested_stem: str,
        resolver: LocationResolver,
    ) -> str:
        """
        Returns the readable stem used in:

            MM-<stem>-<hash>

        Explicit user stem wins unless it is the generic default.
        """

        explicit = requested_stem.strip()

        if explicit and explicit.lower() not in {"locale", "unknown", "auto"}:
            return explicit

        if not members:
            return "locale"

        provisional = GeoGroup.from_members(
            group_id="",
            members=members,
            resolver=resolver,
        )

        site = provisional.site_guess.strip()

        if site and site.lower() != "unknown":
            return site

        return "locale"
