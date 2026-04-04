"""whirlwind.core.state

PURPOSE:
  Centralized, in-process runtime state (config + feature flags) for the
  interactive shell and timing decorators.

BEHAVIOR
  - Store the loaded configuration dictionary.
  - Store runtime toggles (verbose/quiet/debug, timing enabled).
  - Provide an optional hook for reporting timing events without hard-coding UI.

PUBLIC
  - `AppState`
  - `STATE` (singleton)

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

TimerReporter = Callable[[str, float], None]


@dataclass
class AppState:
    config: Dict[str, Any] = field(default_factory=dict)

    verbose: bool = False
    quiet: bool = False
    debug: bool = False

    timing_enabled: bool = True
    timer_reporter: Optional[TimerReporter] = None


STATE = AppState()

