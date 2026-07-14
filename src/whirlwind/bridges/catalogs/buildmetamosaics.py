import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from whirlwind.adapters.io.csv_rows import write_dict_csv
from whirlwind.adapters.io.idmanifest import IDManifest

from whirlwind.geography.geogroup import (
        GeoRow, GeoGroup, read_georows
)
from whirlwind.geography.location import (
        FolderHintLocationResolver, LocationResolver
) 

from whirlwind.filesystem.spatialbranch import (
    BuildSpatialBranch,
    SpatialBranchSummary,
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
    stem: str = "unknown"
    metamosaic_manifest_name: str = "metamosaic.csv"
    metamosaic_summary_name: str = "metamosaic_summary.csv"
    root_manifest_name: str = "manifest.csv"
    spatial_branch_manifest_name: str = "branches.csv"
    overlap_threshold: float = 0.97
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
    spatial_branch_manifest_path: Path
    spatial_branches_written: int
    branch_summaries: tuple[SpatialBranchSummary, ...]
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
        with face.phase(1, 5, "loading metadata and manifest from request..."):
            geo_rows = read_georows(request.metadata_path)
            manifest_rows = self._read_manifest_rows(request.manifest.path)

        with face.phase(2, 5, "building footprint intersection graph..."):
            groups, pairs = self._intersect_groups(geo_rows)

        with face.phase(3, 5, "assigning metamosaic ids..."):
            mm_by_mid: dict[str, str] = {} 
            mm_alias_by_mid: dict[str, str] = {}
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
                
                mm_alias = FileID.metamosaic_alias(member_ids)
                mmid = FileID.metamosaic(member_ids, stem=stem)

                for mid in member_ids:
                    mm_by_mid[mid] = mmid
                    mm_alias_by_mid[mid] = mm_alias
                
                geo_groups.append(
                        GeoGroup.from_members(
                            group_id=mmid, 
                            members=members, 
                            resolver=resolver,
                            )
                        ) 
        rows_with_metamosaic_ids = self._add_metamosaic_fields(
            manifest_rows,
            mm_by_mid,
            mm_alias_by_mid,
        )

        with face.phase(4, 5,"building canonical spatial branches...",):

            branch_builder = BuildSpatialBranch()

            branch_summaries, branch_assignments = (
                branch_builder.build(
                    manifest_rows=rows_with_metamosaic_ids,
                    geo_rows=geo_rows,
                    threshold=request.overlap_threshold,
                )
            )

            enriched_manifest_rows = (
                branch_builder.enrich_manifest(
                    rows_with_metamosaic_ids,
                    branch_assignments,
                )
            ) 

        summaries = self._summary_rows_from_groups(geo_groups)
        
        with face.phase(5, 5, "writing metamosaic tree and manifests..."):
            
            spatial_branch_manifest_path = (
                request.run_tree.manifest_dir / request.spatial_branch_manifest_name
            )

            write_dict_csv(
                spatial_branch_manifest_path,
                [
                    summary.record()
                    for summary in branch_summaries
                ],
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
            
            self._write_tree_metadata(
                    tree=request.run_tree, 
                    metadata_name=request.metadata_path.name, 
                    root_manifest_name=request.root_manifest_name, 
                    metamosaic_manifest_name=request.metamosaic_manifest_name, 
                    metamosaic_summary_name=request.metamosaic_summary_name, 
                    enriched_manifest_rows=enriched_manifest_rows, 
                    geo_rows=geo_rows, 
                    geo_groups=geo_groups
                    )

        return Result(
            metamosaic_manifest_path=metamosaic_manifest_path,
            root_manifest_path=root_manifest_path,
            metamosaics_written=len(set(mm_by_mid.values())),
            summaries=summaries,
            mosaics_seen=len(geo_rows),
            intersections=len(pairs), 

            spatial_branch_manifest_path=spatial_branch_manifest_path,
            spatial_branches_written=len(branch_summaries),
            branch_summaries=tuple(branch_summaries),

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

    def _add_metamosaic_fields(
        self,
        rows: list[dict[str, str]],
        mm_by_mid: dict[str, str],
        mm_alias_by_mid: dict[str, str],
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []

        for row in rows:
            mid = (
                row.get("mosaic_id")
                or row.get("file_id")
                or row.get("id")
                or ""
            )

            enriched = dict(row)
            enriched["metamosaic_id"] = mm_by_mid.get(mid, "")
            enriched["metamosaic_alias"] = (
                mm_alias_by_mid.get(mid, "")
            )

            # These are assigned by BuildSpatialBranch afterward.
            enriched.pop("branch_id", None)
            enriched.pop("canonical_mosaic_id", None)

            out.append(enriched)

        return out


    def _membership_rows(
        self,
        rows: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        return [
            {
                "canonical_mosaic_id": row.get(
                    "canonical_mosaic_id","",),
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

            if record.metamosaic_id:
                tree.spatial_branch_for(record).ensure()

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
            return "unknown"

        provisional = GeoGroup.from_members(
            group_id="",
            members=members,
            resolver=resolver,
        )

        site = provisional.site_guess.strip()

        if site and site.lower() != "unknown":
            return site

        return "unknown"

    def _write_tree_metadata(
        self,
        *,
        tree: RunTree,
        metadata_name: str,
        root_manifest_name: str,
        metamosaic_manifest_name: str,
        metamosaic_summary_name: str,
        enriched_manifest_rows: list[dict[str, str]],
        geo_rows: list[GeoRow],
        geo_groups: list[GeoGroup],
    ) -> None:

        metadata_by_mid: dict[str, dict[str, str]] = {
                row.mosaic_id: dict(row.row)
                for row in geo_rows
                } 
        summary_by_mmid: dict[str, dict[str, str]] = {
                group.group_id: group.to_metamosaic_record()
                for group in geo_groups 
                }
        manifest_rows_by_mmid: dict[str, list[dict[str,str]]] = {} 
        
        for row in enriched_manifest_rows: 
            mmid = row.get("metamosaic_id","")
            if mmid: 
                manifest_rows_by_mmid.setdefault(mmid, []).append(row)

        for manifest_row in enriched_manifest_rows: 
            record = MosaicRecord.from_row(manifest_row)
            branch = tree.branch_for(record).ensure() 

            mid = record.mosaic_id 
            mmid = record.metamosaic_id or ""

            write_dict_csv(
                    branch.metadata_dir / root_manifest_name, 
                    [manifest_row],
                ) 

            metadata_row = metadata_by_mid.get(mid)
            if metadata_row:
                branch_metadata_row = {
                    **metadata_row,
                    "metamosaic_id": mmid,
                    "branch_id": manifest_row.get("branch_id", ""),
                }

                write_dict_csv(
                    branch.metadata_dir / metadata_name,
                    [branch_metadata_row],
                )

        # Write metamosaic-level metadata.
        for mmid, member_manifest_rows in manifest_rows_by_mmid.items():
            mm_tree = tree.metamosaic_tree(mmid).ensure()

            write_dict_csv(
                mm_tree.metadata_dir / root_manifest_name,
                member_manifest_rows,
            )

            write_dict_csv(
                mm_tree.metadata_dir / metamosaic_manifest_name,
                self._membership_rows(member_manifest_rows),
            )

            summary_row = summary_by_mmid.get(mmid)
            if summary_row:
                write_dict_csv(
                    mm_tree.metadata_dir / metamosaic_summary_name,
                    [summary_row],
                )

            member_metadata_rows: list[dict[str, str]] = []

            for manifest_row in member_manifest_rows:
                mid = (
                    manifest_row.get("mosaic_id")
                    or manifest_row.get("file_id")
                    or manifest_row.get("id")
                    or ""
                )

                metadata_row = metadata_by_mid.get(mid)
                if not metadata_row:
                    continue

                member_metadata_rows.append(
                    {
                        **metadata_row,
                        "metamosaic_id": mmid,
                        "branch_id": manifest_row.get("branch_id", ""),
                    }
                )

            if member_metadata_rows:
                write_dict_csv(
                    mm_tree.metadata_dir / metadata_name,
                    member_metadata_rows,
                )
