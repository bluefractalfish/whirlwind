"""whirlwind.tools.pathfinder 

    PURPOSE:
        - helpers for retrieving path objects 
    BEHAVIOR:
        - given directory io return path objects for iteration, etc 

    PUBLIC:
        get_root_(out_dir) -> Path 
        find_home_(start, markers = (.git,projext.toml)) -> Path 
        search_for_extension(input path, extensions = .tiff, tif) -> iterable(path)
"""



from pathlib import Path 
from typing import Iterable 

def get_root_(out_dir: str | Path) -> Path:
    root = Path(out_dir).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    return root

def build_path(*parts: str | Path, make_dirs: bool = True) -> tuple[int, Path | None]:
    """
    Returns:
        (1, path) -> successful and path exists
        (0, path) -> successful but path does not exist
        (3, None) -> failure
    """
    try:
        path = Path(parts[0])
        for part in parts[1:]:
            path = path / part

        path = path.expanduser().resolve(strict=False)

        if make_dirs:
            path.mkdir(parents=True, exist_ok=True)

        return (1, path) if path.exists() else (0, path)

    except Exception:
        raise

def find_home_(start: Path | None = None, markers: Iterable[str] = (".git", "pyproject.toml")) -> Path:
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

def search_for_extension(input_path: Path, 
                         extensions: tuple[str,...]=(".tiff",".tif")) -> Iterable[Path]:
    for p in input_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions: 
            yield p


def dir_walker_(input_dir: Path, limit: int = 20) -> Iterable[Path]:
    return sorted((p for p in input_dir.iterdir()), key=lambda p: p.stat().st_size, reverse=True)[:limit]

