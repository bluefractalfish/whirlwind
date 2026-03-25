from whirlwind.imps import * 


class AppState:
    config: Dict[str, Any] = field(default_factory=dict)
    VERBOSE: bool = False
    QUIET: bool = False
    DEBUG: bool = False 
    LOG: bool = False 
    TIME: bool = True 



STATE = AppState()
