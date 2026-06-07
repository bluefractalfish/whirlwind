# rich (UI / logging)
from __future__ import annotations 
import os 
import shutil
import time 
import textwrap 
from dataclasses import dataclass, field 
from typing import Any, Iterable, Iterator 

from contextlib import contextmanager 

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

def make_console() -> Console:
    width = get_width()
    return Console(width=width)

def get_width() -> int: 
    return int(
            os.environ.get(
                "WW_WIDTH",
                shutil.get_terminal_size(fallback=(140,24)).columns,
            )
         )

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
    #width: int = 600

@dataclass
class Interface:
    """
    Terminal User Interface handles all printing to the users console. Using the rich API 
    this class initiates a Console object then prints to the terminal using console.print() 

    """
    _console: Console = field(default_factory=make_console) 
    theme: Theme = field(default_factory=Theme)
    

    def print(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.text}]{message}[/]")
     
    def info(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.info}]{message}[/]")
    def debug(self, message: Any ) -> None:
        self._console.print(f"  [{self.theme.debug}]{message}[/]")
    def warning(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.warn}]{message}[/]")
    def error(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.error}]{message}[/]")
    def success(self, message: Any ) -> None:
        self._console.print(f"[{self.theme.text}]{message}[/]")
    
    def format_s(self, seconds: float) -> str:
        if seconds < 1: 
            return f"{seconds * 1000:.0f}ms"
        if seconds < 60:
            return f"{seconds:.2f}s"
        minutes = int(seconds // 60)
        rest = seconds % 60 
        return f"{minutes}m {rest:.1f}s"
 
    def row(self, key: str, value: Any, *, key_style: str = "bold white", value_style: str | None = None) -> None:
        value_style = value_style or self.theme.text
        self._console.print(f"[{key_style}]{key}[/]: [{value_style}]{value}[/]")
    def info_row(self, key: str, value: Any, *, key_style: str = "bold white", value_style: str | None = None) -> None:
        value_style = value_style or self.theme.text
        self._console.print(f"[{key_style}]{key}[/]: [{value_style}]{value}[/]")

    def prog_row(self, key: str, value: Any) -> None:
        self._console.print(f"[dim][{key}][/]: [bold white]{value}[/]")

    def rule(self, title: str = "", *, style: str | None = None) -> None:
        self._console.print(Rule(title=title, style=style or self.theme.rule))
    def div(self) -> None:
        div = "-" * 10 
        self._console.print(div)
    def process(self, in_name: str, process_name: str, out_name: str) -> None:
        self._console.print(f"[{self.theme.info}]{in_name}[/] > [{self.theme.warn}]{process_name}[/] > [{self.theme.info}]{out_name}[/]")
    
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
    
    @contextmanager 
    def phase(self, index: int, total: int, message: str, delay: float=0.2) -> Iterator[None]:
        start = time.perf_counter()
        self._console.print(
            f"[{index}/{total}][{self.theme.info}] {message}[/]"
        )
        
        time.sleep(delay)

        try:
            yield
        except Exception:
            elapsed = time.perf_counter() - start - delay 
            self._console.print(
                f"[{self.theme.error}]failed [/]" 
                f"{message}" 
                f"[dim][{self.format_s(elapsed)}][/]"
            )
            time.sleep(delay)
            raise
        else:
            elapsed = time.perf_counter() - start - delay 
            self._console.print(
                f"[{self.theme.success}]DONE [/]"
                f"[dim][{self.format_s(elapsed)}][/]"
            )
            time.sleep(delay)

    def exception(self, msg: str = "error") -> None:
        self._console.print(f"[{self.theme.error}]{msg}[/]")
        self._console.print_exception(show_locals=True)

    def table(
        self,
        columns: list[str],
        rows: list[list],
        title: str = "",
        *,
        expand: bool = True,
    ) -> None:
        """Generic Rich table."""
        table = Table(
            title=title,
            box=None,
            expand=expand,
        )

        for col in columns:
            table.add_column(
                col,
                overflow="fold",
            )

        for row in rows:
            table.add_row(*[str(value) for value in row])

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


    def print_bbox(
        self,
        minx: float,
        miny: float,
        maxx: float,
        maxy: float,
        title: str = "WGS84 BOUNDS",
        member_ids: list[str] | tuple[str, ...] = (),
        width: int | None = None,
    ) -> str:

        width = width or min(self._console.width, 100)

        if width < 32:
            lines = [
                title,
                f"NW {minx:.4f} {maxy:.4f}",
                f"NE {maxx:.4f} {maxy:.4f}",
                f"SW {minx:.4f} {miny:.4f}",
                f"SE {maxx:.4f} {miny:.4f}",
            ]

            if member_ids:
                lines.append("members:")
                lines.extend(f"  {member_id}" for member_id in member_ids)

            return "\n".join(lines)

        inner = width - 2

        TL, TR, BL, BR = "┏", "┓", "┗", "┛"
        H, V = "━", "┃"

        def clamp(text: str) -> str:
            if len(text) <= inner:
                return text
            if inner <= 1:
                return text[:inner]
            return text[: inner - 1] + "…"

        def line(text: str = "") -> str:
            return V + clamp(text).ljust(inner) + V

        def center(text: str = "") -> str:
            return V + clamp(text).center(inner) + V

        def divider() -> str:
            return V + ("─" * inner) + V

        def pair_line(left: str, right: str) -> str:
            space = inner - len(left) - len(right)

            if space < 2:
                raise ValueError("too narrow for paired bbox layout")

            return V + left + (" " * space) + right + V

        def fmt_corner(name: str, lon: float, lat: float, precision: int) -> str:
            return f"{name} {lon:.{precision}f} {lat:.{precision}f}"

        if width >= 80:
            precision = 6
        elif width >= 56:
            precision = 5
        else:
            precision = 4

        nw = fmt_corner("NW", minx, maxy, precision)
        ne = fmt_corner("NE", maxx, maxy, precision)
        sw = fmt_corner("SW", minx, miny, precision)
        se = fmt_corner("SE", maxx, miny, precision)

        x_range = f"lon {minx:.{precision}f} -> {maxx:.{precision}f}"
        y_range = f"lat {miny:.{precision}f} -> {maxy:.{precision}f}"

        lines: list[str] = [
            TL + (H * inner) + TR,
        ]

        try:
            lines.extend(
                [
                    pair_line(nw, ne),
                    line(),
                    center(title),
                    center(x_range),
                    center(y_range),
                    line(),
                    pair_line(sw, se),
                ]
            )
        except ValueError:
            lines.extend(
                [
                    center(title),
                    line(),
                    line(nw),
                    line(ne),
                    line(sw),
                    line(se),
                    line(),
                    line(x_range),
                    line(y_range),
                ]
            )

        if member_ids:
            lines.append(divider())
            lines.append(line("member mosaics"))

            wrapped_members = textwrap.wrap(
                ", ".join(str(member_id) for member_id in member_ids),
                width=inner,
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            )

            for row in wrapped_members:
                lines.append(line(row))

        lines.append(BL + (H * inner) + BR)

        return "\n".join(lines)


    def member_ids_block(
        self,
        member_ids: list[str] | tuple[str, ...],
        *,
        width: int = 20,
        title: str = "members",
    ) -> str:
        width = max(width, int(get_width()))
        inner = width - 2

        V = "┃"
        H = "━"

        def line(text: str = "") -> str:
            return V + text[:inner].ljust(inner) + V

        lines = [
            "┏" + (H * inner) + "┓",
            line(title),
            "┃" + ("─" * inner) + "┃",
        ]

        for member_id in member_ids:
            lines.append(line(f"• {member_id}"))

        lines.append("┗" + (H * inner) + "┛")

        return "\n".join(lines)

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

        def __init__(self, width: int=get_width(), done_char: str = "#", empty_char: str = "-") -> None:
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


