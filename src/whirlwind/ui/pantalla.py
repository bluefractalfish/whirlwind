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

install(show_locals=True)

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
        self._console.print(f"[{self.theme.text}]{message}[/]")
    
    def info(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.info}]{message}[/]")
    def debug(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.debug}]{message}[/]")
    def warning(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.warn}]{message}[/]")
    def error(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.error}]{message}[/]")

    def success(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.text}]{message}[/]")

    def row(self, key: str, value: Any, *, key_style: str = "bold white", value_style: str | None = None) -> None:
        value_style = value_style or self.theme.text
        self._console.print(f"[{key_style}]{key}[/]: [{value_style}]{value}[/]")

    def rule(self, title: str | None = None, *, style: str | None = None) -> None:
        self._console.print(Rule(title=title, style=style or self.theme.rule))
    def div(self) -> None:
        div = "-" * self.theme.width 
        self._console.print(div)

    def process(self, in_name: str, process_name: str, out_name: str) -> None:
        self._console.print(f"[{self.theme.info}]{in_name}[/] > [{self.theme.warn}]{process_name}[/] > [{self.theme.info}]{out_name}[/]")

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

        table = Table(title=title,box=None)

        for col in columns:
            table.add_column(col)

        for r in rows:
            table.add_row(*[str(v) for v in r])

        self._console.print(table)

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


