""" whirlwind.config 

    PURPOSE: 
        - marks directory as regular Python package for stable import namespace 
        - provide single entrypoint build_config for config normalization and merging 
    PUBLIC: 
        - DEFAULT_CONFIG 
        - build_config(path: str) -> dict 



"""

from __future__ import annotations 

import yaml 

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from whirlwind.ui import face 
from .defaults import DEF_CON 
from .merge import deep_merge 
from .schema import normalize

__all__ = ["DEF_CON", "build_config"] 

@dataclass 
class Config:
    raw: Dict[str,Any]
    default: Dict[str,Any]
    merged : Dict[str,Any]

    def __init__(self, config_doc):
        self.raw = load_yaml(config_doc)
        self.default = DEF_CON
        self.merged = self.build()
    
    def build(self) -> Dict[str, Any]:
        if not isinstance(self.raw,dict):
            face.error("config error: raw config must be dictionary")
            raise ValueError
        normalized = normalize(self.raw)
        merged = deep_merge(self.default, normalized)
        self.merged = merged
        return merged

    def parse(self, command:str, subcommand: str) -> Dict[str,Any]:
        try:
            command_cfg = self.merged.get(command) or {}
            subcommand_cfg = command_cfg.get(subcommand) or {}
        except Exception:
            face.error(f"config error: configuration for {command} not found")
            return {}
        if subcommand == {}:
            face.error(f"config error: configuration for {command} not found")
            return {}
        return subcommand_cfg
         

    def table(self) -> None:
        face.div()
        face.info("configuration setting")
        face.div()
        face.print_dictionary(self.merged)
    

def load_yaml(path_str: str) -> Dict[str,Any]: 
    path = Path(path_str).expanduser().resolve()
    with path.open("r",encoding="utf-8") as f: 
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        face.error("config file must contain top level mapping")
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
