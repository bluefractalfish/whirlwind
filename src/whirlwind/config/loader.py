from pathlib import Path 
from typing import Any, Dict 

import yaml 

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

