from whirlwind.imps import *
from ..ui.tui import TUI 

ui = TUI()

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
            level: str = "DEBUG",
            component: str | None = None,
            run_id: str | None = None,
            ) -> None:

        ui.row(f"looking for log at",f"{path}")
        dir =  Path(path).expanduser().resolve()
        self.js = dir/"wind.jsonl"
        self.hr = dir/"wind.log"
        dir.parent.mkdir(parents=True,exist_ok=True)
        ui.info("opening logs: ")
        ui.row(f"    for machines",f"{self.js}")
        ui.row(f"    for humans",f"{self.hr}")
        self.level = level.upper()
        self.component = component or "app"
        self.run_id = run_id or "ww"+str(uuid.uuid4())[:5]
        ui.success(f"opening log for iteration {self.run_id} at {self._utc_now()}")


    def child(self, component: str, **context: Any) -> "ChildLogger":
        return ChildLogger(self, component=component, context=context)

    def _utc_now(self) -> str:
        dt =  datetime.now(timezone.utc).isoformat(timespec="minutes") 
        dt = dt[2:].replace("-","") + "Z"
        return dt

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


    def _write_js(self, record: dict[str, Any]) -> None:
        with self.js.open("a", encoding="utf-8") as l:
            l.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    def _write_hr(self, record: dict[str, Any]) -> None:
        ln =  "\n  ___"
        for a in record.values():
            ln = ln + f":{a}:"
        with self.hr.open("a", encoding="utf8") as hl:
            hl.write(ln + "\n")
    def log(
            self,
            level: str,
            message: str | None = None, 
            component: str | None=None,
            **data: Any ,
            ) -> dict[str, Any]:

        level = level.upper()
        if not self._enabled(level):
            return {}
        record = {
                "level": level,
                "run_id": self.run_id,
                "ts": self._utc_now(),
                "component": component or self.component,
                "message": str(message),
                "data": "" if data == {} else self._normalize(data) 
                }

        self._write_js(record)
        self._write_hr(record)
        return record 

    def debug(self, message: str, **data: Any) -> None:
        self.log("DEBUG",  message, **data)

    def info(self, message: str, **data: Any) -> None:
        self.log("INFO", message,  **data)

    def warning(self, message: str, **data: Any) -> None:
        self.log("WARN", message,  **data)

    def error(self, message: str, **data: Any) -> None:
        self.log("ERROR",  message,  **data) 

    def breakpoint(self) -> None:
        self.log("DEBUG", "breakpoint")

class ChildLogger:
    def __init__(self, base: Logger, component: str, context: Mapping[str, Any] | None = None) -> None:
        self.base = base 
        self.component = component 
        self.context = dict(context or {})

    def _merge(self, data: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.context)
        merged.update(data)  
        return merged 

    def debug(self,  message: str, **data: Any) -> None:
        self.base.log("DEBUG",  message, component=self.component, **self._merge(data))

    def info(self,  message: str, **data: Any) -> None:
        self.base.log("INFO",  message, component=self.component, **self._merge(data))

    def warning(self,  message: str, **data: Any) -> None:
        self.base.log("WARN",  message, component=self.component, **self._merge(data))

    def error(self,  message: str, **data: Any) -> None:
        self.base.log("ERROR",  message, component=self.component, **self._merge(data))

    @contextmanager
    def timed(self,  message: str = "", **data: Any):
        with self.base.timed( message=message, component=self.component, **self._merge(data)):
            yield
