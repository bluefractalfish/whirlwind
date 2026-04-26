"""
whirlwind.adapters.io.csv_rows

Concrete CSV/JSONL row-writing adapter.

"""


import csv
import json
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence 

def safe_jsonable(value: Any) -> Any:
    """
    Convert arbitrary Python values into JSON-safe values.

    This is used before flattening nested metadata into CSV cells.
    GDAL objects, Path objects, CRS objects, etc. fall back to str(value).
    """

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (list, tuple)):
        return [safe_jsonable(v) for v in value]

    if isinstance(value, dict):
        return {str(k): safe_jsonable(v) for k, v in value.items()}

    return str(value)


def flatten_for_csv(row: Mapping[str, Any]) -> dict[str, str]:
    """
    Convert one nested metadata row into flat CSV-safe string values.

    Nested dict/list/tuple values are encoded as JSON strings.
    Scalars are converted to strings.
    None becomes an empty cell.
    """

    out: dict[str, str] = {}

    for key, value in row.items():
        key_s = str(key)

        if value is None:
            out[key_s] = ""
            continue

        if isinstance(value, (dict, list, tuple)):
            out[key_s] = json.dumps(
                safe_jsonable(value),
                ensure_ascii=False,
                sort_keys=True,
            )
            continue

        out[key_s] = str(safe_jsonable(value))

    return out


def collect_fieldnames(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """
    Return sorted union of all row keys.

    This allows rows with slightly different metadata fields, which happens
    with GDAL extended/full metadata.
    """

    names: set[str] = set()

    for row in rows:
        names.update(str(k) for k in row.keys())

    return sorted(names)


def write_dict_csv(
    path: str | Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: list[str] | None = None,
) -> Path:
    """
    Write dictionaries to CSV.

    Memory note
    -----------
    This function receives a list of rows. That is fine for small/medium
    metadata manifests. For very large catalogs, add a streaming writer later.
    """

    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    flat_rows = [flatten_for_csv(row) for row in rows]

    columns = fieldnames or collect_fieldnames(flat_rows)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for row in flat_rows:
            writer.writerow({key: row.get(key, "") for key in columns})

    return out


def write_csv(
    path: str | Path,
    rows: list[Mapping[str, Any]],
    columns: list[str],
) -> int:
    """
    Write rows using explicit columns.

    Return codes:
        0 -> success
        1 -> failure
    """

    try:
        write_dict_csv(path, rows, fieldnames=columns)
        return 0
    except Exception:
        return 1


def read_csv_one_row(path: str | Path) -> dict[str, str]:
    """
    Read the first data row from a CSV.

    Used when per-mosaic metadata already exists and the bridge wants to reuse
    it for aggregate metadata.
    """

    src = Path(path).expanduser().resolve()

    with src.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)

    return dict(row or {})


def append_jsonl(data: Mapping[str, Any], path: str | Path) -> Path:
    """
    Append one dictionary as a JSONL row.

    Useful for experiment logs or incremental processing logs.
    """

    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(safe_jsonable(dict(data)), ensure_ascii=False, sort_keys=True))
        f.write("\n")

    return out
