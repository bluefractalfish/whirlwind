from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import Command
from ..utils import pathfinder as pf
from ..utils import geo
from ..utils import readwrite as rwr
#from .tessera import tiles 
#from .tessera.tiles import Tiler


class IngestCommand(Command):
    name = "ingest"

    def run(self, tokens: list[str], config: dict[str, Any]) -> int:
        if not tokens:
            raise ValueError("ingest requires a subcommand")

        subcommand = tokens[0]
        input = tokens[1]

        if subcommand == "tiles":
            conf = self._config_tiler(input,config)
            tiler = Tiler.source_(conf)
            tiler.run()
            return 0

        raise ValueError(f"unknown ingest subcommand: {subcommand}")

    def _config_tiler(self, input: str, config: dict[str, Any]) -> dict[str, Any]:
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


@dataclass(frozen=True)
class QParams:
    dtype: str
    scale: str
    p_low: float
    p_high: float
    per_band: bool
    stats: str
    num_samples: int


@dataclass
class Tiler:
    tp: TParams
    qp: QParams

    @classmethod
    def source_(cls, cfg: dict[str, Any]) -> "Tiler":

        uris = list(rwr._iter_uris(cfg["input"]))
        out_dir = pf._get_root_(cfg["out"])

        tp = TParams(
            uris=uris,
            out_dir=out_dir,
            tile_size=cfg["tile_size"],
            stride=cfg["stride"],
            drop_partial=cfg["drop_partial"],
            shard_size=cfg["shard_size"],
            shard_prefix=cfg["shard_prefix"],
            manifest_kind=cfg["manifest"],
        )

        qp = QParams(
            dtype=cfg["dtype"],
            scale=cfg["scale"],
            p_low=cfg["p_low"],
            p_high=cfg["p_high"],
            per_band=cfg["per_band"],
            stats=cfg["stats"],
            num_samples=cfg["num_samples"],
        )

        return cls(tp=tp, qp=qp)

    def _dirs(self, idx) -> tuple[Path, Path]:
        shards_dir = self.tp.out_dir / str(idx) / "shards"
        manifest_dir = self.tp.out_dir / str(idx) / "manifest"
        shards_dir.mkdir(parents=True, exist_ok=True)
        manifest_dir.mkdir(parents=True, exist_ok=True)
        return shards_dir, manifest_dir

    def run(self) -> None:
        idx = 0
        for uri in self.tp.uris:
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
            idx = idx + 1

            mosaic_id, seen, written, errors, skipped = summary
            print(
                f"{mosaic_id} "
                f"seen={seen} written={written} errors={errors} skipped={skipped}"
            )
