"""whirlwind.utils.logger

PURPOSE:
  Lightweight structured logger for Whirlwind.

PUBLIC:
  - `Logger`
  - `ChildLogger`

"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class Logger:
    LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

    def __init__(self, log_dir: str | Path, level: str = "DEBUG", component: str | None = None, run_id: str | None = None) -> None:
        self.dir = Path(log_dir).expanduser().resolve()
        self.dir.mkdir(parents=True, exist_ok=True)

        self.js = self.dir / "wind.jsonl"
        self.hr = self.dir / "wind.log"

        self.level = level.upper()
        self.component = component or "app"
        self.run_id = run_id or ("ww" + str(uuid.uuid4())[:5])

        self.info("logger initialized")

    def child(self, component: str, **context: Any) -> "ChildLogger":
        return ChildLogger(self, component=component, context=context)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _enabled(self, level: str) -> bool:
        return self.LEVELS[level] >= self.LEVELS.get(self.level, 10)

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(k): self._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._normalize(v) for v in value]
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        return value

    def _write_js(self, record: dict[str, Any]) -> None:
        with self.js.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _write_hr(self, record: dict[str, Any]) -> None:
        msg = record.get("message")
        data = record.get("data")
        line = f"{record.get('ts')} {record.get('level')} {record.get('component')} {msg}"
        if data not in (None, "", {}):
            line += f" | {data}"
        with self.hr.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log(self, level: str, message: str | None = None, component: str | None = None, **data: Any) -> dict[str, Any]:
        level = level.upper()
        if level not in self.LEVELS:
            level = "INFO"
        if not self._enabled(level):
            return {}

        record = {
            "level": level,
            "run_id": self.run_id,
            "ts": self._utc_now(),
            "component": component or self.component,
            "message": "" if message is None else str(message),
            "data": "" if not data else self._normalize(data),
        }
        self._write_js(record)
        self._write_hr(record)
        return record

    def debug(self, message: str, **data: Any) -> None:
        self.log("DEBUG", message, **data)

    def info(self, message: str, **data: Any) -> None:
        self.log("INFO", message, **data)

    def warning(self, message: str, **data: Any) -> None:
        self.log("WARN", message, **data)

    def error(self, message: str, **data: Any) -> None:
        self.log("ERROR", message, **data)

    @contextmanager
    def timed(self, message: str, component: str | None = None, **data: Any):
        start = datetime.now(timezone.utc)
        try:
            yield
        finally:
            end = datetime.now(timezone.utc)
            self.info(message, component=component, elapsed_seconds=(end - start).total_seconds(), **data)


class ChildLogger:
    def __init__(self, base: Logger, component: str, context: Mapping[str, Any] | None = None) -> None:
        self.base = base
        self.component = component
        self.context = dict(context or {})

    def _merge(self, data: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.context)
        merged.update(data)
        return merged

    def child(self, component: str, **context: Any) -> "ChildLogger":
        merged = dict(self.context)
        merged.update(context)
        return ChildLogger(self.base, component=component, context=merged)

    def debug(self, message: str, **data: Any) -> None:
        self.base.log("DEBUG", message, component=self.component, **self._merge(data))

    def info(self, message: str, **data: Any) -> None:
        self.base.log("INFO", message, component=self.component, **self._merge(data))

    def warning(self, message: str, **data: Any) -> None:
        self.base.log("WARN", message, component=self.component, **self._merge(data))

    def error(self, message: str, **data: Any) -> None:
        self.base.log("ERROR", message, component=self.component, **self._merge(data))

    @contextmanager
    def timed(self, message: str, **data: Any):
        with self.base.timed(message, component=self.component, **self._merge(data)):
            yield

