"""whirlwind.utils.timer

PURPOSE:
  Lightweight timing utilities for profiling and iteration.

PUBLIC
  - `StopWatch`
  - `timed(label='')`

"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from whirlwind.core.state import STATE

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class StopWatch:
    label: str = ""
    enabled: bool = True
    start: Optional[float] = None
    end: Optional[float] = None
    elapsed: Optional[float] = None

    def __enter__(self) -> "StopWatch":
        if self.enabled:
            self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.enabled and self.start is not None:
            self.end = time.perf_counter()
            self.elapsed = self.end - self.start


def timed(label: str = "") -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not STATE.TIME:
                return fn(*args, **kwargs)
            start = time.perf_counter()
            result = fn(*args, **kwargs)
            seconds = time.perf_counter() - start
            #if STATE.time_reporter is not None:
            #    STATE.time_reporter(label or fn.__name__, seconds)
            return result
        return wrapper  # type: ignore[return-value]
    return decorator

