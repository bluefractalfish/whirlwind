""" whirlwind.config 

    PURPOSE: 
        - marks directory as regular Python package for stable import namespace 
        - provide single entrypoint build_config for config normalization and merging 
    PUBLIC: 
        - DEFAULT_CONFIG 
        - build_config(path: str) -> dict 



"""

from __future__ import annotations 


from typing import Any, Dict, Optional 
import yaml 
from .default import DEFAULT_CONFIG 
from .merge import deep_merge 
from .schema import ensure_sections, normalize, validate

__all__ = ["DEFAULT_CONFIG", "build_config"] 


def build_config(path: str) -> Dict[str,Any]:
    raw = load_yaml(path) 
    if not isinstance(raw, dict): 
        raise ValueError("IN BUILD_CONFIG: raw config must be dictionary ")
    normalized = normalize(raw) 
    merged = deep_merge(DEFAULT_CONFIG, normalized)
    merged = ensure_sections(merged)
    validate(merged) 
    return merged 
