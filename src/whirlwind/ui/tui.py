from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.rule import Rule
from rich.progress import Progress, ProgressColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TextColumn, Task
from rich.panel import Panel
from rich.align import Align


class TUI:
    """
    Terminal User Interface handles all printing to the users console. Using the rich API 
    this class initiates a Console object then prints to the terminal using console.print() 
    
    if initatied without "DEBUG" only tables and progress bars are printed

    the available printing modes are: 
        c_box( message, optional title, alignment) -> prints a panel containing message,
            optional title, and optional alignment. defaults to centered (c) and takes r, l
        print(message) -> prints standard white message
        info(message) -> prints bold white message
        row(c1, c2) -> prints bold c1: regular c2
        success(message) -> prints green success signal
        error(msg) -> prints error in bold red
        div(title) -> prints page divider
    """

    LEVELS = { 
            "INFO": 0,
            "DEBUG": 10,
            "PROGRESS": 20,
            "ERROR": 30
            }

    def __init__(self, lvl="PROGRESS"):
        level = lvl.upper()
        self.level = self.LEVELS[level]
        self._console = Console()
    
    def c_box(self, msg:str, title: str | None=None, align: str = "c", l = "DEBUG" ) -> None:
        l=l.upper()
        if self.LEVELS[l] < self.level: return
        if align == "c": 
            self._console.print(Panel(Align.center(msg),title=title))
        if align == "r":
            self._console.print(Panel(Align.right(msg), title=title))
        if align == "l":
            self._console.print(Panel(Align.left(msg), title=title))
    # generic printing
    def print(self, msg: str, l = "DEBUG") -> None:
        l=l.upper()
        if self.LEVELS[l] < self.level: return
        self._console.print(f"[white]{msg}[/]")

    def info(self, msg: str, l = "DEBUG") -> None:
        l=l.upper()
        if self.LEVELS[l] < self.level: return
        self._console.print(f"[bold white]{msg}[/]")

    def row(self, c1: str, c2, l="DEBUG") -> None:
        l=l.upper()
        if self.LEVELS[l] < self.level: return
        self._console.print(f"[bold white]{c1}[/]: [white]{c2}[/]")

    def success(self, msg: str = "+", l="DEBUG") -> None:
        l=l.upper()
        if self.LEVELS[l] < self.level: return
        self.div(f"[green]{msg}[/]", style="bold green")

    def warn(self, msg: str, l="DEBUG") -> None:
        l=l.upper()
        if self.LEVELS[l] < self.level: return
        self._console.print(f"[yellow]{msg}[/]")

    def error(self, msg: str,) -> None:
        self._console.print(f"[bold red]{msg}[/]")

    def div(self, title: str | None=None, style: str="white", l="PROGRESS"):
        l=l.upper()
        if self.LEVELS[l] < self.level: return
        self._console.print(Rule(title, style=style))

    # table display
    def table(self, title: str, columns: list[str], rows: list[list], l="PROGRESS") -> None:
        l=l.upper()
        if self.LEVELS[l] < self.level: return

        table = Table(title=title,box=None,show_lines=False)

        for col in columns:
            table.add_column(col)

        for r in rows:
            table.add_row(*[str(v) for v in r])

        self._console.print(table)

    # progress bar
    def progress(self, l="PROGRESS"):
        l=l.upper()
        if self.LEVELS[l] < self.level: return

        return Progress(
            TextColumn("[progress.description]{task.description}"),
            TextColumn("["),
            AsciiBar(),
            TextColumn("]"),
            TextColumn("{task.percentage:>3.0f}"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            transient=False,
            console=self._console,)

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
