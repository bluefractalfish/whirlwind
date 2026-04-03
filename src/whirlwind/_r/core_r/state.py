
from __future__ import annotations 

from typing import Dict, Any, Callable, Optional 
from dataclasses import field 

TimerReporter = Callable[[str, float], None]

class AppState:
    config: Dict[str, Any] = field(default_factory=dict)
    VERBOSE: bool = False
    QUIET: bool = False
    DEBUG: bool = False 
    LOG: bool = False 
    TIME: bool = True 

    time_reporter: Optional[TimerReporter] = None



STATE = AppState()
