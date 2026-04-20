from __future__ import annotations

import json
import csv 
from pathlib import Path
from typing import Any, Mapping
from whirlwind.tools.formatters import flatten_for_csv, fieldnames 


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


def write_csv(out, rows, columns) -> int:
    try:
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k,"") for k in columns})
        return 0
    except:
        return 1

def write_dict_csv(path: Path, data: list[dict[str, Any]]) -> Path:

   flat_rows = [flatten_for_csv(d) for d in data]
   columns = fieldnames(flat_rows)
   with path.open("w", newline="", encoding="utf-8") as f:
       w = csv.DictWriter(f, fieldnames=columns)
       w.writeheader()
       for row in flat_rows:
           w.writerow({k: row.get(k, "") for k in columns})
   return path

def read_csv_one_row(path: Path) -> dict[str, str]:
    with open(path, mode='r', newline="") as f:
        csvreader = csv.DictReader(f)
        row = next(csvreader or None)
        return row or {}

"""
def append_csv(data: Mapping[str, Any], path: str | Path) -> Path:
    "append to existing csv"

    :out: = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True,exist_ok=True)

    with out.open("a", encoding="utf-8") as f:
        f.write(csv)
"""
