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

    


