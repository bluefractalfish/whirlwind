"""whirlwind.config.merge 

    PURPOSE: 
        deterministic deep-merge for config layer 
    BEHAVIOUR: 
        merge nested mappings without mutating inputs 
    PUBLIC: 
        deep_merge(base, override) -> dict 

"""

from __future__ import annotations 
from typing import Any, Dict 

def deep_merge(base: Dict[str, Any], override: Dict[str,Any]) -> Dict[str,Any]: 
    result: Dict[str, Any] = dict(base) 
    for k,v in override.items():
        if k in result and isinstance(result[k],dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k],v)
        else: 
            result[k] = v 
    return result 

def normalize(obj: Any) -> Any: 
    if isinstance(obj, dict):
        return {
                str(key).replace("-","_"): normalize(value) 
                for key, value in obj.items()
            }
    if isinstance(obj, list):
        return [normalize(item) for item in obj] 
    return obj 
