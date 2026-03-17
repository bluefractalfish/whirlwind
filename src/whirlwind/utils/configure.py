import yaml 
from typing import Any 
from pathlib import Path
from ..ui.tui import TUI 


ui = TUI()
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
        ui.error(f"PathError: {path_str}")
        return {}
    path = Path(path_str).expanduser().resolve()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        ui.error("config file must contain top level mapping")
        return {} 
    ui.row(f"loading configuration from", f"{path_str}")
    return normalize_(data) 

