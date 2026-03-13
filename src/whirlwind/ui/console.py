from rich.console import Console 
from rich.theme import Theme 

_THEME = Theme({
    "info" : "white",
    "data" : "bold white",
    "warn" : "bold yellow",
    "error": "bold red",
    "success" : "bold green",
    "muted" : "dim",
    })  

def init_console() -> Console:
    return Console(theme=_THEME)
