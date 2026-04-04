from whirlwind.imps import * 
from ..core.state import STATE 
from ..ui.tui import PANT

class StopWatch():
    def __init__(self, label: str=""):
        self.enabled = True
        self.label = label 
        self.start = None 
        self.end = None 
        self.elapsed = None
    def __enter__(self):
        if self.enabled:
            self.start = time.perf_counter()
        return self 
    def __exit__(self, exc_type, exc, tb):
        if self.enabled:
            self.end = time.perf_counter() 
            self.elapsed = self.end - self.start 
        return self 
            


def timed(label: str = ""):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args,**kwargs):
            if not STATE.TIME:
                return fn(*args, **kwargs)
            start = time.perf_counter()
            result = fn(*args,**kwargs)
            end = time.perf_counter()
            PANT.info(f"{label or fn.__name__} took {end-start:.4f}s","QUIET")
            return result 
        return wrapper 
    return decorator 
