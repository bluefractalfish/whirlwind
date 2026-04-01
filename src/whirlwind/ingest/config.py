"""whirlwind.ingest.config
    PURPOSE:
        Interpret Whirlwind config for the `ingest tiles` pipeline and build typed
        params.
    BEHAVIORS:
        - Merge config layers (global + ingest.global + ingest.tiles) with defaults.
        - Validate key constraints (stride, percentile bounds).
        - Resolve input URIs from csv/dir/glob.
        - Resolve output root directory.
    PUBLIC: 
        - parse_cfg(input_source, config) -> dict
        - build_params(input_source, config) -> (TParams, QParams)

"""
from __future__ import annotations
from typing import Any, Dict, Tuple
from whirlwind.ingest.params import QParams, TParams
from whirlwind.io.inputs import iter_uris
from whirlwind.tools import pathfinder as pf

DEFAULTS: Dict[str, Any] = {
    "input": None,
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

def parse_cfg(input_source: str, config: Dict[str, Any]) -> Dict[str,Any]:
    root_global = config.get("global", {})
    ingest_cfg = config.get("ingest", {})
    ingest_global = ingest_cfg.get("global", {}) if isinstance(ingest_cfg,dict) else {}
    tiles_cfg = ingest_cfg.get("tiles", {}) if isinstance(ingest_cfg, dict) else {}

    if not isinstance(root_global, dict):
        root_global = {}
    if not isinstance(ingest_global, dict):
        ingest_global = {}
    if not isinstance(tiles_cfg, dict):
        tiles_cfg = {}
    cfg: Dict[str, Any] = dict(DEFAULTS)
    cfg["input"] = input_source
    cfg.update(root_global)
    cfg.update(ingest_global)
    cfg.update(tiles_cfg)

    if cfg["input"] is None:
        ValueError("ingest.tiles requires config value: input")
    if cfg["stride"] is None:
        cfg["stride"] = cfg["tile_size"]
    if int(cfg["tile_size"]) <= 0:
        raise ValueError("tile_size must be > 0")
    if int(cfg["stride"]) > int(cfg["tile_size"]):
        raise ValueError("stride must be > 0")
    if str(cfg.get("scale")) == "percentile":
        if not (0 <= float(cfg["p_low"]) < float(cfg["p_high"]) <= 100):
             raise ValueError("percentile scaling requires 0 <= p_low < p_high <= 100")
    return cfg

def experiment_overrides(perm: dict[str, Any]) -> dict[str, Any]:
    cfg = {
        "global": dict(DEFAULTS.get("global", {})),
        "ingest": {
            "global": dict(DEFAULTS.get("ingest", {}).get("global", {})),
            "tiles": dict(DEFAULTS.get("ingest", {}).get("tiles", {})),
        },
    }
    cfg["ingest"]["tiles"].update(perm)
    return cfg


def build_params(input_source: str, config: Dict[str, Any]) -> Tuple[TParams, QParams]:
    cfg = parse_cfg(input_source, config)
    uris = list(iter_uris(str(cfg["input"])))
    out_dir = pf.get_root_(cfg["out"])
    tp = TParams(
        uris=uris,
        out_dir=out_dir,
        tile_size=int(cfg["tile_size"]),
        stride=int(cfg["stride"]),
        drop_partial=bool(cfg["drop_partial"]),
        shard_size=int(cfg["shard_size"]),
        shard_prefix=str(cfg["shard_prefix"]),
        manifest_kind=str(cfg["manifest"]),
    )
    qp = QParams(
        dtype=str(cfg["dtype"]),
        scale=str(cfg["scale"]),
        p_low=float(cfg["p_low"]),
        p_high=float(cfg["p_high"]),
        per_band=bool(cfg["per_band"]),
        stats=str(cfg["stats"]),
        num_samples=int(cfg["num_samples"]),
    )
    tp.validate()
    qp.validate()
    return tp, qp
