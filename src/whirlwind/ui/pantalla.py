# rich (UI / logging)
from __future__ import annotations 
from dataclasses import dataclass, field 
from typing import Any, Iterable

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    ProgressColumn,
    Task,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.traceback import install

from whirlwind.core.state import STATE 

#install(show_locals=True)

@dataclass 
class Theme: 
    text: str = "white"
    info: str = "bold white"
    debug: str = "dim cyan"
    warn: str = "yellow"
    error: str = "bold red"
    success: str = "bold green"
    muted: str = "grey62"
    rule: str = "white"
    panel_border: str = "white"
    width: int = 60

@dataclass
class Pantalla:
    """
    Terminal User Interface handles all printing to the users console. Using the rich API 
    this class initiates a Console object then prints to the terminal using console.print() 

    """
    _console: Console = field(default_factory=Console) 
    theme: Theme = field(default_factory=Theme)

    def print(self, message: Any ) -> None:
        self._console.print(f"  [{self.theme.text}]{message}[/]")
    
    def info(self, message: Any ) -> None:
        self._console.print(f"  [{self.theme.info}]{message}[/]")
    def debug(self, message: Any ) -> None:
        self._console.print(f"  [{self.theme.debug}]{message}[/]")
    def warning(self, message: Any ) -> None:
        self._console.print(f"  [{self.theme.warn}]{message}[/]")
    def error(self, message: Any ) -> None:
        self._console.print(f"  [{self.theme.error}]{message}[/]")
    def success(self, message: Any ) -> None:
        self._console.print(f"  [{self.theme.text}]{message}[/]")
    
    
    def row(self, key: str, value: Any, *, key_style: str = "bold white", value_style: str | None = None) -> None:
        value_style = value_style or self.theme.text
        self._console.print(f"  [{key_style}]{key}[/]: [{value_style}]{value}[/]")
    def info_row(self, key: str, value: Any, *, key_style: str = "bold white", value_style: str | None = None) -> None:
        value_style = value_style or self.theme.text
        self._console.print(f"  [{key_style}]{key}[/]: [{value_style}]{value}[/]")

    def prog_row(self, key: str, value: Any) -> None:
        self._console.print(f"    [dim][{key}][/]: [bold white]{value}[/]")

    def rule(self, title: str = "", *, style: str | None = None) -> None:
        self._console.print(Rule(title=title, style=style or self.theme.rule))
    def div(self) -> None:
        div = "-" * self.theme.width 
        self._console.print(div)
    def process(self, in_name: str, process_name: str, out_name: str) -> None:
        self._console.print(f"  [{self.theme.info}]{in_name}[/] > [{self.theme.warn}]{process_name}[/] > [{self.theme.info}]{out_name}[/]")
    
    def header(self, msg: str) -> None:
        self._console.print(Align.center(f"[{self.theme.info}]_{msg}_[/]"))

    def panel(self, msg: Any, *, title: str | None = None, align: str = "center", border_style: str | None = None) -> None:
        if align == "left":
            body = Align.left(str(msg))
        elif align == "right":
            body = Align.right(str(msg))
        else:
            body = Align.center(str(msg))

        self._console.print(
            Panel(
                body,
                title=title,
                border_style=border_style or self.theme.panel_border,
            )
        )

    def exception(self, msg: str = "error") -> None:
        self._console.print(f"[{self.theme.error}]{msg}[/]")
        self._console.print_exception(show_locals=True)

    def table(self,columns: list[str], rows: list[list],title: str = "" ) -> None:
        """ generic print table for rich """
        table = Table(title=title,box=None)

        for col in columns:
            table.add_column(col)

        for r in rows:
            table.add_row(*[str(v) for v in r])

        self._console.print(table)

    def print_dictionary(
        self,
        data: dict[str, Any],
        *,
        title: str = "",
        key_header: str = "KEY",
        value_header: str = "VAL",
        separator: str = ".",
        show_lines: bool = False,
        expand: bool = False,
            ) -> None:
        """
        nested dictionary as a Rich table.

        - nested dicts are flattened into dotted paths
        - lists/tuples/sets are rendered as compact strings
        - scalar values are converted to strings
        """

        table = Table(
            title=title,
            show_lines=show_lines,
            expand=expand,
        )
        table.add_column(key_header, no_wrap=True)
        table.add_column(value_header)

        for key_path, value in self._flatten_mapping(data, separator=separator):
            table.add_row(key_path, self._format_value(value))

        self._console.print(table)

    def _flatten_mapping(
        self,
        data: dict[str, Any],
        *,
        parent: str = "",
        separator: str = ".",
    ) -> Iterable[tuple[str, Any]]:
        """
        Yield flattened (path, value) pairs from nested dictionaries.
        """
        for key, value in data.items():
            key_str = str(key)
            path = f"{parent}{separator}{key_str}" if parent else key_str

            if isinstance(value, dict):
                if value:
                    yield from self._flatten_mapping(
                        value,
                        parent=path,
                        separator=separator,
                    )
                else:
                    yield path, None
            else:
                yield path, value

    def _format_value(self, value: Any) -> str:
        """
        Convert values to readable strings for table display.
        """
        if value is None:
            return "None"

        if isinstance(value, bool):
            return "True" if value else "False"

        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(v) for v in value) if value else "[]"

        return str(value)

    # progress bar
    def progress(self):

        return Progress(
            TextColumn("[progress.description]{task.description}"),
            TextColumn("["),
            AsciiBar(),
            TextColumn("]"),
            TextColumn("{task.percentage:>3.0f}"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            transient=False,
            console=self._console,
            )

class AsciiBar(ProgressColumn):

        def __init__(self, width: int=40, done_char: str = "#", empty_char: str = "-") -> None:
            super().__init__()
            self.width=width 
            self.done_char=done_char
            self.empty_char=empty_char
        def render(self, task: Task) -> Text:
            if task.total is None:
                return Text("["+"-"*self.width+"]")
            total = task.total or 0
            completed = min(task.completed, total) if total else task.completed 
            ratio = 0.0 if total == 0 else completed / total 
            filled = min(self.width, max(0, int(ratio*self.width)))
            empty = self.width-filled 

            bar =  "#" * filled + "-" * empty 
            return Text(bar)


