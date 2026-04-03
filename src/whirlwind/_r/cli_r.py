""" whirlwind.cli 


    PURPOSE: 
        - entrypoint for whirlwind cli 

    BEHAVIOR:
        - parse cli arguments 
        - call build_config 
        - bootstrap app + shell 

    PUBLIC:
        - main(argv=None) -> int 
"""

from __future__ import annotations

import argparse 
import sys 
from pathlib import Path 
from typing import Any, Dict, Optional

from rich.traceback import install 

from whirlwind._r.config_r import Config
from whirlwind._r.core_r import bootstrapp  

#install(show_locals=True)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whirlwind")
    parser.add_argument( 
                        "--config",
                        type=str,
                        default="config.yaml",
                        help="path to yaml config. defaults to config.yaml"
                    )
    return parser 


def main(argv: Optional[list[str]] = None) -> int:
    config_doc = build_parser().parse_args(argv).config
    
    config = Config(config_doc)
    
    app = bootstrapp(config) 
    #shell = WShell(app, config) 
    #return shell.run() 

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


