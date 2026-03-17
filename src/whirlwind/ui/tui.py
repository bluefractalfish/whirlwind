from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, BarColumn, TimeElapsedColumn, TextColumn
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
        self._console.print(f"[cyan]{msg}[/]")

    def row(self, c1: str, c2) -> None:
        self._console.print(f"[cyan]{c1}[/]: [white]{c2}[/]")

    def success(self, msg: str) -> None:
        self._console.print(f"[bold green]{msg}[/]")

    def warn(self, msg: str) -> None:
        self._console.print(f"[yellow]{msg}[/]")

    def error(self, msg: str) -> None:
        self._console.print(f"[bold red]{msg}[/]")

    def div(self, title: str | None=None, style: str="white"):
        self._console.print(Rule(title, style=style))

    # table display
    def table(self, title: str, columns: list[str], rows: list[list]) -> None:

        table = Table(title=title)

        for col in columns:
            table.add_column(col)

        for r in rows:
            table.add_row(*[str(v) for v in r])

        self._console.print(table)

    # progress bar
    def progress(self):

        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=self._console,
        )
