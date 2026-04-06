""" whirlwind.config.schema 
    
    PURPOSE: 
        - normalize and valdidate the configuration dictionary 
    BEHAVIOR: 
        - normalize keys recursivley 
        - ensure expected top-level sections exist (global ingest inspect, etc...)
        - performe lightweight validation 
    
    PUBLIC: 
        Config
"""

from __future__ import annotations 

from typing import Any, Dict 


import yaml 

from dataclasses import dataclass
from pathlib import Path
from whirlwind.tools.pathfinder import find_home_
from typing import Any, Dict, Tuple
from .defaults import DEF_CON 
from .merge import deep_merge 


__all__ = ["DEF_CON", "build_config"] 

@dataclass 
class Config:
    raw: Dict[str,Any]
    default: Dict[str,Any]
    merged : Dict[str,Any]

    def __init__(self, config_doc):
        config_path = str(find_home_() / config_doc)
        self.raw = load_yaml(config_path)
        self.default = DEF_CON
        self.merged = self.build()
    
    def build(self) -> Dict[str, Any]:
        if not isinstance(self.raw,dict):
            raise ValueError("config error: raw config must be dictionary")
        normalized = normalize(self.raw)
        merged = deep_merge(self.default, normalized)
        self.merged = merged
        return merged

    def parse(self, command:str, subcommand: str) -> Dict[str,Any]:
        try:
            command_cfg = self.merged.get(command) or {}
            subcommand_cfg = command_cfg.get(subcommand) or {}
        except Exception:
            raise ValueError(f"config error: configuration for {command} not found")
            return {}
        if subcommand == {}:
            raise ValueError(f"config error: configuration for {command} not found")
            return {}
        return subcommand_cfg
         
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
def normalize(obj: Any) -> Any: 
    if isinstance(obj, dict):
        return {
                str(key).replace("-","_"): normalize(value) 
                for key, value in obj.items()
            }
    if isinstance(obj, list):
        return [normalize(item) for item in obj] 
    return obj 

    


