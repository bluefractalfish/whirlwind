""" whirlwind.config.defaults 

    PURPOSE: 
        - centeral location for configuration defaults 

    BEHAVIOURS: 
        - provide a predictable baseline config dict so downstream 
        code can assume top-level sections always exist 

    PUBLIC: 
        - DEFAULT_CONFIG 

"""

from __future__ import annotations 

from typing import Any, Dict 

DEFAULT_CONFIG: Dict[str, Any] = { 
                                  "global": {
                                      "version": "",
                                      "log": "./artifacts/logs",
                                    },
                                  "ingest": {
                                      "global": {},
                                      "tiles": {},
                                    }, 
                                  "inspect": {},
                                  "experiments": {},
}
