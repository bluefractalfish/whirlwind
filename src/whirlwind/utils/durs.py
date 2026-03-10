"""
utilites to help with finding, creating, measuring directories

"""

from pathlib import Path

def _get_root_(root: str) -> Path:
    return Path(root).expanduser().resolve()

def _find_home_(start: Path | None = None, markers: Iterable[str] = (".git", "pyproject.toml")) -> Path:
    """
    Walk upward from `start` (default: this file's directory) until a marker is found.
    Markers can be files or directories.
    """
    here = (start or Path(__file__).resolve()).resolve()
    if here.is_file():
        here = here.parent

    for p in (here, *here.parents):
        for m in markers:
            if (p / m).exists():
                return p
    # Fallback: last resort, anchor to this file's directory
    return here

def _mkdir_(p: Path) -> None:
    p.mkdir(parents=True,exist_ok=True)
