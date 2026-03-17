"""
Tiler class handler 
"""
from typing import Any
from pathlib import Path
from dataclasses import dataclass
from ...utils import datahelp as dh
from ...utils import ids
from ...utils import readwrite as rwr
from ...utils import pathfinder as pf
from ...utils import geo
from ...ui.tui import TUI 

ui = TUI()
def _tesselate_(tokens: list[str], config: dict[str, Any], log) -> int:
    if len(tokens) !=  1:
        ui.error("tiling expects one input field")
    input = tokens[0]
    t = Tiler(input, config,log)
    t.run()
    return 0



@dataclass
class Tiler:
    tp: TParams
    qp: QParams

    def __init__(self, i: str, c: dict[str, Any], log):
        self.log = log
        cfg = self._parse_config(i,c)
        ui.info("attempting to open IO paths...")
        uris = list(rwr._iter_uris(cfg["input"]))
        out_dir = pf._get_root_(cfg["out"])
    
        self.tp = TParams(
            uris=uris,
            out_dir=out_dir,
            tile_size=cfg["tile_size"],
            stride=cfg["stride"],
            drop_partial=cfg["drop_partial"],
            shard_size=cfg["shard_size"],
            shard_prefix=cfg["shard_prefix"],
            manifest_kind=cfg["manifest"],
        )

        self.qp = QParams(
            dtype=cfg["dtype"],
            scale=cfg["scale"],
            p_low=cfg["p_low"],
            p_high=cfg["p_high"],
            per_band=cfg["per_band"],
            stats=cfg["stats"],
            num_samples=cfg["num_samples"],
        )

    def _parse_config(self, input: str, config: dict[str, Any]) -> dict[str, Any]:
        root_global = config.get("global", {})
        ingest_cfg = config.get("ingest", {})
        ingest_global = ingest_cfg.get("global", {})
        tiles_cfg = ingest_cfg.get("tiles", {})

        if not isinstance(root_global, dict):
            root_global = {}
        if not isinstance(ingest_cfg, dict):
            ingest_cfg = {}
        if not isinstance(ingest_global, dict):
            ingest_global = {}
        if not isinstance(tiles_cfg, dict):
            tiles_cfg = {}
        
        # ensure all params are set
        cfg = {
            "input": input,
            "out": "./artifacts",
            "tile_size": 512,
            "stride": None,
            "drop_partial": True,
            "shard_size": 4096,
            "shard_prefix": "tiles",
            "manifest": "csv",
            "dtype": "float32",
            "scale": "none",
            "p_low": 2.0,
            "p_high": 98.0,
            "per_band": True,
            "stats": "sample",
            "num_samples": 2048,
        }

        cfg.update(root_global)
        cfg.update(ingest_global)
        cfg.update(tiles_cfg)

        if cfg["input"] is None:
            raise ValueError("ingest.tiles requires config value: input")

        if cfg["stride"] is None:
            cfg["stride"] = cfg["tile_size"]

        if cfg["tile_size"] <= 0:
            raise ValueError("tile_size must be > 0")

        if cfg["stride"] <= 0:
            raise ValueError("stride must be > 0")

        if cfg["scale"] == "percentile":
            if not (0 <= cfg["p_low"] < cfg["p_high"] <= 100):
                raise ValueError("percentile scaling requires 0 <= p_low < p_high <= 100")

        return cfg


    def _dirs(self, idx) -> tuple[Path, Path]:
        shards_dir = self.tp.out_dir / str(idx) / "shards"
        manifest_dir = self.tp.out_dir / str(idx) / "manifest"
        shards_dir.mkdir(parents=True, exist_ok=True)
        manifest_dir.mkdir(parents=True, exist_ok=True)
        return shards_dir, manifest_dir

    def run(self) -> None:
        for uri in self.tp.uris:
            idx = ids.uuid_from_path(uri)
            uri = uri.strip()
            if not uri:
                continue
            shards_dir, manifest_dir = self._dirs(idx)

            summary = geo.cut_mosaic(
                uri,
                manifest_dir,
                shards_dir,
                self.qp,
                self.tp,
            )

            mosaic_id, seen, written, errors, skipped = summary
            ui.table(f"tiling summary for {uri}",
                     ["manifest","shards","mosaic id", "seen","written","errors","skipped"],
                     [[shards_dir, manifest_dir, mosaic_id, seen, written, errors, skipped]],
                    )

@dataclass(frozen=True)
class TParams:
    uris: list[str]
    out_dir: Path
    tile_size: int
    stride: int
    drop_partial: bool
    shard_size: int
    shard_prefix: str
    manifest_kind: str
    
    def table(self) -> None:
        title = "TPARAMS"
        c = ["params","value"] 
        r = [
                ["out",self.out_dir],
                ["tile_size", self.tile_size],
                ["stride", self.stride],
                ["shard_size", self.shard_size],
                ["drop_partial", self.drop_partial],
                ["shard_size",self.shard_size]
            ]
        ui.table(title,c,r)


@dataclass(frozen=True)
class QParams:
    dtype: str
    scale: str
    p_low: float
    p_high: float
    per_band: bool
    stats: str
    num_samples: int

    def table(self) -> None:
        title = "QPARAMS"
        c = ["params","values"] 
        r = [
                ["dtype", self.dtype],
                ["scale", self.scale],
                ["p_low", self.p_low],
                ["p_hi", self.p_high],
                ["per_band", self.per_band],
                ["stats", self.stats],
                ["num_sampels", self.num_samples]
            ]
        ui.table(title,c,r)
