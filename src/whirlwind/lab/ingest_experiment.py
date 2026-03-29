from itertools import product
from typing import Any, Iterator

from .config_grid import INGEST_GRID

def _cartesian_(grid: dict[str, Any]) -> Iterator[dict[str, Any]]:
    keys = list(grid.keys())
    values = []
    for k in keys:
        v = grid[k]
        if isinstance(v, list):
            values.append(v)
        else:
            values.append([v])
    for perm in product(*values):
        yield dict(zip(keys, perm))

def _valid_(cfg: dict[str, Any]) -> bool:
    tile_size = cfg.get("tile_size")
    stride = cfg.get("stride")
    scale = cfg.get("scale")
    p_low = cfg.get("p_low")
    p_high = cfg.get("p_high")

    if tile_size is None or tile_size <= 0:
        return False
    if stride is None or stride < 0 or stride > tile_size:
        return False
    if scale == "percentile":
        if p_low is None or p_high is None:
            return False
        if not (0.0 <= p_low < p_high <= 100.0):
            return False
    return True

def list_configs() -> list[dict[str, Any]]:
    return [cfg for cfg in _cartesian_(INGEST_GRID) if _valid_(cfg)]
