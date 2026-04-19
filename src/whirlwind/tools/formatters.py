import json 
from typing import Any 

def safe_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [safe_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): safe_jsonable(v) for k, v in value.items()}
    return str(value)

def flatten_for_csv( row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {} 
    for k, v in row.items(): 
        if isinstance(v, (dict, list, tuple)):
            out[k] = json.dumps(safe_jsonable(v), ensure_ascii=False, sort_keys=True)
        elif v is None:
            out[k] = ""
        else:
            out[k] = str(v)
    return out

def fieldnames(rows: list[dict[str, str]]) -> list[str]: 
    names: set[str] = set()
    for row in rows:
        names.update(row.keys())
    return sorted(names)

