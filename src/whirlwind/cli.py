
from typing import List, Optional
import argparse
#import toolbox from local directory
#from rich.console import Console
#from pathlib import Path
from . import toolbox


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="whirlwind")
    sub = p.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan a directory and summarize files")
    scan.add_argument("root", type=str, help="Root directory to scan")
    scan.add_argument("--top-n", type=int, default=500, help="Show top N largest files (0 disables)")

    args = p.parse_args(argv)

    return toolbox.dispatch(args)

if __name__ == "__main__":
    raise SystemExit(main())

