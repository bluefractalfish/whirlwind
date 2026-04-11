from pathlib import Path 
from typing import Any, Dict 

import yaml 
from .merge import deep_merge, normalize
from .defaults import DEF_CON

def load_config(config_path: str | None) -> Dict[str,Any]:
    """
    load config file. 
    return empty dict if no path given

    """
    if config_path is None:
        # nopath error 
        return {}
    p = Path(config_path)
    if not p.exists():
        # nopath error
        return {}
    with p.open("r",encoding="utf-8") as f: 
        config_data = yaml.safe_load(f) 
    return config_data 

         
def load_yaml(path_str: str) -> Dict[str,Any]: 
    path = Path(path_str).expanduser().resolve()
    with path.open("r",encoding="utf-8") as f: 
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("config file must contain top level mapping")
    return data 

def build_config(config_doc: str) -> Dict[str,Any]:
    raw = load_yaml(config_doc)
    if not isinstance(raw, dict): 
        raise ValueError("IN BUILD_CONFIG: raw config must be dictionary ")
    normalized = normalize(raw) 
    merged = deep_merge(DEF_CON, normalized)
    #merged = ensure_sections(merged)
    #validate(merged) 
    return merged 


