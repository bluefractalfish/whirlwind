from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.rule import Rule
from rich.progress import Progress, ProgressColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TextColumn, Task
from rich.panel import Panel
from rich.align import Align


class TUI:

    def __init__(self):
        self._console = Console()
    
    def c_box(self, msg:str, title: str | None=None ) -> None:
        self._console.print(Panel(Align.center(msg),title=title))
    # generic printing
    def print(self, msg: str) -> None:
        self._console.print(f"[white]{msg}[/]")

    def info(self, msg: str) -> None:
        self._console.print(f"[bold white]{msg}[/]")

    def row(self, c1: str, c2) -> None:
        self._console.print(f"[bold white]{c1}[/]: [white]{c2}[/]")

    def success(self, msg: str) -> None:
        self._console.print(f"[green]{msg}[/]")

    def warn(self, msg: str) -> None:
        self._console.print(f"[yellow]{msg}[/]")

    def error(self, msg: str) -> None:
        self._console.print(f"[bold red]{msg}[/]")

    def div(self, title: str | None=None, style: str="white"):
        self._console.print(Rule(title, style=style))

    # table display
    def table(self, title: str, columns: list[str], rows: list[list]) -> None:

        table = Table(title=title,box=None,show_lines=False)

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
