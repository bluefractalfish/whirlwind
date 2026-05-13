import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from whirlwind.adapters.io.csv_rows import write_dict_csv
from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.domain.filesystem.files import FileID
from whirlwind.domain.filesystem.runtree import RunTree
from whirlwind.domain.geometry.mosaics.mosaic import MosaicRecord
from whirlwind.face import face


@dataclass(frozen=True)
class BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float

    def intersects(self, other: "BBox") -> bool:
        return (
            self.minx <= other.maxx
            and self.maxx >= other.minx
            and self.miny <= other.maxy
            and self.maxy >= other.miny
        )


@dataclass(frozen=True)
class GeoRow:
    mosaic_id: str
    bbox: BBox
    row: dict[str, str]


@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    manifest: IDManifest
    metadata_path: Path
    stem: str = "locale"
    metamosaic_manifest_name: str = "metamosaic.csv"
    root_manifest_name: str = "manifest.csv"
    force: bool = False

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
            geo_rows = self._read_geo_rows(request.metadata_path)
            manifest_rows = self._read_manifest_rows(request.manifest.path)

        with face.phase(2, 4, "building footprint intersection graph..."):
            groups, pairs = self._intersect_groups(geo_rows)

        with face.phase(3, 4, "assigning metamosaic ids..."):
            mm_by_mid: dict[str, str] = {}

            for member_ids in groups:
                mmid = FileID.metamosaic(member_ids, stem=request.stem)
                for mid in member_ids:
                    mm_by_mid[mid] = mmid

        summaries = self._summary_rows(geo_rows, mm_by_mid)

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

    def _read_geo_rows(self, path: Path) -> list[GeoRow]:
        rows: list[GeoRow] = []

        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                mid = (row.get("mosaic_id") or "").strip()
                if not mid:
                    continue

                try:
                    bbox = BBox(
                        minx=float(row["minx_wgs84"]),
                        miny=float(row["miny_wgs84"]),
                        maxx=float(row["maxx_wgs84"]),
                        maxy=float(row["maxy_wgs84"]),
                    )
                except Exception:
                    continue

                rows.append(GeoRow(mosaic_id=mid, bbox=bbox, row=row))

        return rows

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

    def _summary_rows(
        self,
        geo_rows: list[GeoRow],
        mm_by_mid: dict[str, str],
    ) -> tuple[Summary, ...]:
        grouped: dict[str, list[GeoRow]] = {}

        for row in geo_rows:
            mmid = mm_by_mid.get(row.mosaic_id, "")
            if not mmid:
                continue

            grouped.setdefault(mmid, []).append(row)

        summaries: list[Summary] = []

        for mmid, members in sorted(grouped.items()):
            minx = min(m.bbox.minx for m in members)
            miny = min(m.bbox.miny for m in members)
            maxx = max(m.bbox.maxx for m in members)
            maxy = max(m.bbox.maxy for m in members)

            summaries.append(
                Summary(
                    metamosaic_id=mmid,
                    n_mosaics=len(members),
                    site_guess=self._site_guess(members),
                    minx_wgs84=minx,
                    miny_wgs84=miny,
                    maxx_wgs84=maxx,
                    maxy_wgs84=maxy,
                    members=tuple(m.mosaic_id for m in members),
                )
            )

        return tuple(summaries)


    def _site_guess(self, members: list[GeoRow]) -> str:
        """
        Best-effort, hard coded human label for the table.

        This does not affect IDs or grouping. It is only display text.
        """
        text = " ".join(
            str(m.row.get("path") or m.row.get("source_uri") or m.row.get("uri") or "")
            for m in members
        ).lower()

        if "clearlake" in text or "clear_lake" in text or "clear lake" in text:
            return "ClearLake"

        if "norman" in text:
            return "Norman"

        return "unknown"

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
