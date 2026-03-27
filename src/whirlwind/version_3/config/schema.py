""" whirlwind.config.schema 
    
    PURPOSE: 
        - normalize and valdidate the configuration dictionary 
    BEHAVIOR: 
        - normalize keys recursivley 
        - ensure expected top-level sections exist (global ingest inspect, etc...)
        - performe lightweight validation 
    
    PUBLIC: 
        - normalize(obj)->obj 
        - ensure_sections(cfg)->cfg 
            - add command sections here 
        - validate(cfg)-> None 
            - add command sections here 
"""

from __future__ import annotations 

from typing import Any, Dict 

def normalize(obj: Any) -> Any: 
    if isinstance(obj, dict):
        return {
                str(key).replace("-","_"): normalize(value) 
                for key, value in obj.items()
            }
    if isinstance(obj, list):
        return [normalize(item) for item in obj] 
    return obj 


def validate(cfg: Dict[str, Any]) -> None:
    if not isinstance(cfg, dict): 
        raise ValueError("config must be a dict at top level ")
    g = cfg.get("global")
    if g is None or not isinstance(g,dict):
        raise ValueError("config.global must be a mapping")
    ingest = cfg.get("ingest")
    if ingest is None or not isinstance(ingest, dict):
        raise ValueError("config.ingest must be a mapping")

def ensure_sections(cfg: Dict[str, Any]) -> Dict[str, Any]: 
    cfg.setdefault("global", {})
    cfg.setdefault("ingest",{})
    cfg.setdefault("inspect", {}) 
    cfg.setdefault("experiments", {}) 

    ingest = cfg.get("ingest")

    if not isinstance(ingest, dict):
        cfg["ingest"] = {} 
        ingest = cfg["ingest"] 

    ingest.setdefault("global", {})
    ingest.setdefault("tiles", {})

    return cfg
    


