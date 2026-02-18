from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence
from pathlib import Path
from rich.console import Console, Group
from rich.theme import Theme
from rich.text import Text
from rich.rule import Rule
from rich.panel import Panel
from rich.align import Align
from rich.padding import Padding
from rich.table import Table
from rich.columns import Columns
from rich.tree import Tree
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.json import JSON
from rich.progress import (
    Progress,
    BarColumn,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
)
from rich.live import Live
from rich.layout import Layout
from rich.status import Status

_DEFAULT_THEME = Theme (
        {
            "info": "white",
            "ok": "green",
            "warn": "yellow",
            "err": "bold red",
            "dim": "dim",
            "title": "bold",
            }
        )

console = Console(theme=_DEFAULT_THEME, highlight=False)


# status spinner
def status(msg: str) -> Status:
    return console.status(msg)
# print string to terminal
def terminal(string:str, align: str=None) -> None:
    if align == "center":
        console.print(Align.center(string))
    else:
        console.print(string)
def info(msg: str) -> None:
    console.print(msg, style="info")
def ok(msg: str) -> None:
    console.print(msg, style="ok")
def warn(msg: str) -> None:
    console.print(msg, style="warn")
def err(msg: str) -> None:
    console.print(msg, style="err")
def divider(label: str | None=None, style: str = "dim", align: str = "center", characters: str = "-") -> None:
    console.print(Rule(label, style=style, align=align, characters=characters))
# print error to terminal
def error_msg(error: str) -> None:
    msg_in_box(f"[bold red]error: {error}[/bold red]",style="red")
# TASK COMPLETED
def completed_msg(task: str) -> None:
    task = task.upper()
    msg_in_box(f"[bold green]{task} COMPLETED[/bold green]", style="green")
# print simple message as box
def msg_in_box(msg: str, title: str | None=None, style: str = "white"):
    console.print(Panel(Align.center(msg),title=title,border_style=style))
# return text object
def text(string: str, style) -> Text:
    return Text(string,style)
# group tables and print as centered panel
def group(tables: List[Table], title: str) -> None:
    content = Group(*tables)
    console.print(Align.center(Panel.fit(Align.center(content),title=title)))

# initialize table
def set_table(title: str | None=None, style: str | None=None) -> Table:
    return Table(title=title, header_style=style)

#==============#
# PROGRESS BAR #
#==============# 
# create new task for progress
def new_task(progress: Progress, description: str, total=None) -> int:
    return progress.add_task(description,total=total)
# advance task
def advance(progress: Progress, task_id: int, n: int=1) -> None:
    progress.update(task_id, advance=n)
def completed(progress: Progress, task_id: int) -> int:
    return progress.tasks[task_id].completed
def progress(verb: str, noun: str):
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[bold]{verb}[/bold]"),
        TextColumn(f"{noun}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) 

#==============#
# TREES #
#==============# 
def make_tree(label: str, guide_style: str = "info") -> Tree:
    return Tree(label, guide_style=guide_style)

def dir_tree( root: str | Path, *, max_depth: int = 4,
    max_entries_per_dir: int = 200, show_files: bool = True,
    include: Optional[Callable[[Path], bool]] = None, sort: bool = True, ) -> Tree:
    root = Path(root)
    label = f"[bold]{root.name or str(root)}[/bold]"
    tree = Tree(label)

    def _walk(node: Tree, p: Path, depth: int) -> None:
        if depth >= max_depth:
            node.add("[dim]…[/dim]")
            return

        try:
            entries = list(p.iterdir())
        except Exception as e:
            node.add(f"[red]!(cannot read)[/red] [dim]{e}[/dim]")
            return

        if include is not None:
            entries = [e for e in entries if include(e)]

        if sort:
            entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        # cap entries to keep output bounded
        shown = entries[:max_entries_per_dir]
        omitted = len(entries) - len(shown)

        for e in shown:
            if e.is_dir():
                child = node.add(f"[bold]{e.name}[/bold]")
                _walk(child, e, depth + 1)
            else:
                if show_files:
                    node.add(f"[green]{e.name}[/green]")

        if omitted > 0:
            node.add(f"[dim]… {omitted} more[/dim]")

    _walk(tree, root, 0)
    return tree


def print_dir_tree_panel(
    root: str | Path,
    *,
    title: str | None = "directory",
    max_depth: int = 10,
    max_entries_per_dir: int = 200,
    show_files: bool = True,
    include: Optional[Callable[[Path], bool]] = None,
) -> None:
    t = dir_tree(
        root,
        max_depth=max_depth,
        max_entries_per_dir=max_entries_per_dir,
        show_files=show_files,
        include=include,
    )
    console.print(
        Align.center(Panel.fit(
            Align.center(t),
            title=title,
            border_style="white",
        )
    ))

