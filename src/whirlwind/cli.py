
from typing import List, Optional
import argparse
#import toolbox from local directory
from rich.console import Console
from pathlib import Path
from . import toolbox


def main(argv: Optional[List[str]] = None) -> int:
    console=Console()
    p = argparse.ArgumentParser(prog="whirlwind")
    sub = p.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan a directory and summarize files")
    scan.add_argument("root", type=str, help="Root directory to scan")
    scan.add_argument("--top-n", type=int, default=500, help="Show top N largest files (0 disables)")

    args = p.parse_args(argv)

    if args.cmd == "scan":
        root = Path(args.root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            console.print(f"[bold red]error:[/bold red] not a directory: {root}")
            return 2

        stats = toolbox.scan_directory(root, top_n=args.top_n)
        toolbox.render_scan_report(root, stats)
        return 0

    return 1



if __name__ == "__main__":
    raise SystemExit(main())

