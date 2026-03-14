"""
handles all logging
"""

from __future__ import annotations

import json
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

class Logger:
    LEVELS = {
            "DEBUG": 10,
            "INFO": 20,
            "WARN": 30,
            "ERROR": 40,
            }

    def __init__(
            self,
            path: str | Path,
            level: str = "INFO",
            component: str | None = None,
            run_id: str | None = None,
            ) -> None:

        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.level = level.upper()
        self.component = component or "app"
        self.run_id = run_id or str(uuid.uuid4())[:6]

    def child(self, component: str, **context: Any) -> "ChildLogger":
        return ChildLogger(self, component=component, context=context)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _enabled(self, level: str) -> bool:
        return self.LEVELS[level] >= self.LEVELS[self.level]

    def _normalize(self, value: Any) -> Any:
        if isinstance(value,Path):
            return str(value) 
        if isinstance(value, dict):
            return {str(k): self._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._normalize(v) for v in value]
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value) 
        return value


    def _write(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as l:
            l.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def log(
            self,
            level: str,
            event: str,
            message: str, 
            component: str | None=None,
            **data: Any,
            ) -> dict[str, Any]:

        level = level.upper()
        if not self._enabled(level):
            return {}
        record = {
                "ts": self._utc_now(),
                "level": level,
                "run_id": self.run_id,
                "component": component or self.component,
                "event": event,
                "message": message,
                "data": self._normalize(data)
                }
        self._write(record)
        return record 

    def debug(self, event: str, message: str, **data: Any) -> None:
        self.log("DEBUG", event, message, **data)

    def info(self, event: str, message: str, **data: Any) -> None:
        self.log("INFO", event, message,  **data)

    def warning(self, event: str, message: str, **data: Any) -> None:
        self.log("WARN", event, message,  **data)

    def error(self, event: str, message: str, **data: Any) -> None:
        self.log("ERROR", event, message,  **data) 

    def exception(self, event: str, exc: BaseException, message: str = "", **data: Any) -> None:
        self.log(
            "ERROR",
            event,
            message or str(exc),
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            traceback=traceback.format_exc(),
            **data,
        )

    def log_config(self, config: Any, event: str = "config_loaded") -> None:
        payload = self._normalize(config)
        self.info(event, "Configuration recorded", config=payload)

    @contextmanager
    def timed(self, event: str, message: str = "", **data: Any):
        start = datetime.now(timezone.utc)
        self.info(f"{event}_start", message or "Started", **data)
        try:
            yield
        except Exception as exc:
            end = datetime.now(timezone.utc)
            self.exception(
                f"{event}_failed",
                exc,
                message="Timed operation failed",
                started_at=start.isoformat(timespec="seconds"),
                ended_at=end.isoformat(timespec="seconds"),
                duration_s=(end - start).total_seconds(),
                **data,
            )
            raise
        else:
            end = datetime.now(timezone.utc)
            self.info(
                f"{event}_done",
                "Completed",
                started_at=start.isoformat(timespec="seconds"),
                ended_at=end.isoformat(timespec="seconds"),
                duration_s=(end - start).total_seconds(),
                **data,
            )

class ChildLogger:
    def __init__(self, base: Logger, component: str, context: Mapping[str, Any] | None = None) -> None:
        self.base = base 
        self.component = component 
        self.context = dict(context or {})

    def _merge(self, data: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.context)
        merged.update(data)  
        return merged 

    def debug(self, event: str, message: str, **data: Any) -> None:
        self.base.log("DEBUG", event, message, component=self.component, **self._merge(data))

    def info(self, event: str, message: str, **data: Any) -> None:
        self.base.log("INFO", event, message, component=self.component, **self._merge(data))

    def warning(self, event: str, message: str, **data: Any) -> None:
        self.base.log("WARN", event, message, component=self.component, **self._merge(data))

    def error(self, event: str, message: str, **data: Any) -> None:
        self.base.log("ERROR", event, message, component=self.component, **self._merge(data))

    def exception(self, event: str, exc: BaseException, message: str = "", **data: Any) -> None:
        self.base.exception(event, exc, message=message, component=self.component, **self._merge(data))

    @contextmanager
    def timed(self, event: str, message: str = "", **data: Any):
        with self.base.timed(event, message=message, component=self.component, **self._merge(data)):
            yield
