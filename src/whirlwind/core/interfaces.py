"""whirlwind.core.interfaces

Purpose:
  Small set of structural interfaces (Protocols) used across packages.

Responsibilities:
  - Provide a stable typing contract for logging without forcing a concrete
    logger implementation or introducing import cycles.

Public API:
  - `LoggerProtocol`
  - `NullLogger`

Why it exists:
  Protocols (PEP 544) let ingest and commands depend on behavior, not concrete classes.
"""

from __future__ import annotations

from typing import Any, Protocol


class LoggerProtocol(Protocol):
    def child(self, component: str, **context: Any) -> "LoggerProtocol": ...

    def debug(self, message: str, **data: Any) -> None: ...
    def info(self, message: str, **data: Any) -> None: ...
    def warning(self, message: str, **data: Any) -> None: ...
    def error(self, message: str, **data: Any) -> None: ...


class NullLogger:
    def child(self, component: str, **context: Any) -> "NullLogger":
        return self

    def debug(self, message: str, **data: Any) -> None:
        return

    def info(self, message: str, **data: Any) -> None:
        return

    def warning(self, message: str, **data: Any) -> None:
        return

    def error(self, message: str, **data: Any) -> None:
        return

