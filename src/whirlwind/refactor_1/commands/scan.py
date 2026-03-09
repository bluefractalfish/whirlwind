"""
owns all scan logic
"""
import argparse
from dataclasses import dataclass 

from .base import Command 

# SCAN ###############################################
@dataclass
class ScanCommand(Command):
    name: str = "scan"

    def configure(self, subparser: argparse._SubParsersAction) -> None:
        parser = subparser.add_parser(
                self.name,
                help="Scan a directory and sumarize files",
            )
        parser.add_argument(
                "root", type=str,
                help=" ROOT to be scanned"
            )
        parser.add_argument(
                "--top-n", type=int, default=500,
                help="show top N largest files, default 500"
            )

    def run(self, args: argparse.Namespace) -> int:
        return toolbox.dispatch_scan(args)
