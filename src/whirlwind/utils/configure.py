import yaml 
from typing import Any 
import shlex 
from pathlib import Path



def normalize_(data: Any) -> Any:
    if isinstance(data, dict):
        return {
                str(key).replace("-","_"): normalize_(value) 
                for key, value in data.items()
            }
    if isinstance(data, list):
        return [normalize_(item) for item in data] 
    return data 

def load_(path_str: str | None) -> dict[str, Any]:
    if not path_str:
        # throw error if wrong path
        return {}
    path = Path(path_str).expanduser().resolve()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("config file must contain top level mapping")
    return normalize_(data) 

