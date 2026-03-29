from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def append_jsonl(data: Mapping[str, Any], path: str | Path) -> Path:
    """
    Append one dictionary as a single JSON line.
    experiment/result rows written incrementally.
    """
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, sort_keys=True))
        f.write("\n")

    return out
