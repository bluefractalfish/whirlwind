""" whirlwind.config 

    PURPOSE: 
        - marks directory as regular Python package for stable import namespace 
        - provide single entrypoint build_config for config normalization and merging 
    PUBLIC: 
        - DEFAULT_CONFIG 
        - build_config(path: str) -> dict 



"""

from __future__ import annotations 

from .schema import Config
