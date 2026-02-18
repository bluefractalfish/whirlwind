# rich imports
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn
)
from rich.table import Table
from rich.text import Text
from rich.align import Align

console = Console()

# print string to terminal
def terminal(string:str, align: str=None) -> None:
    if align == "center":
        console.print(Align.center(string))
    else:
        console.print(string)
def banner(string:str | None=None) -> None:
    console.print(Rule(string))
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
