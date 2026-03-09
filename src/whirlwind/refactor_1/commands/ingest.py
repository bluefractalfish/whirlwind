"""
owns all ingestion logic
"""


import argparse
from dataclasses import dataclass 

from .base import Command 

# INGEST #############################################

class IngestCommand(Command):
    name = "ingest"

    def configure(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(
            self.name,
            help="Ingestion workflow",
        )

        ingest_subparsers = parser.add_subparsers(dest="ingest_cmd", required=True)

        self._configure_tiles(ingest_subparsers)

    def _configure_tiles(self, subparsers: argparse._SubParsersAction) -> None:
        tiles = subparsers.add_parser(
            "tiles",
            help="Tile whole mosaics into shards + manifest",
        )

        self._add_input_args(tiles)
        self._add_tiling_args(tiles)
        self._add_shard_args(tiles)
        self._add_quantization_args(tiles)

    def _add_input_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--input",
            type=str,
            default=None,
            help="Directory or glob for GeoTIFFs",
        )
        parser.add_argument(
            "--input-csv",
            type=str,
            default=None,
            help="CSV with a 'uri' column",
        )
        parser.add_argument(
            "--out",
            type=str,
            default=None,
            help="Output directory",
        )

    def _add_tiling_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--tile-size", type=int, default=512)
        parser.add_argument(
            "--stride",
            type=int,
            default=None,
            help="Default: tile-size (non-overlapping)",
        )
        parser.add_argument(
            "--drop-partial",
            action="store_true",
            default=True,
            help="Drop partial edge tiles",
        )
        parser.add_argument(
            "--keep-partial",
            action="store_false",
            dest="drop_partial",
            help="Keep partial edge tiles",
        )

    def _add_shard_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--shard-size", type=int, default=4096)
        parser.add_argument("--shard-prefix", type=str, default="tiles")
        parser.add_argument(
            "--manifest",
            choices=["parquet", "csv", "none"],
            default="parquet",
        )

    def _add_quantization_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dtype",
            choices=["float32", "uint16", "uint8"],
            default="float32",
            help="Output dtype",
        )
        parser.add_argument(
            "--scale",
            choices=["none", "minmax", "percentile"],
            default="none",
            help="Scaling strategy",
        )
        parser.add_argument("--p-low", type=float, default=0.5)
        parser.add_argument("--p-high", type=float, default=99.5)
        parser.add_argument(
            "--stats",
            choices=["sample", "compute"],
            default="sample",
        )
        parser.add_argument("--num-samples", type=int, default=2048)
        parser.add_argument("--resume", action="store_true", default=False)

    def run(self, args: argparse.Namespace) -> int:
        return toolbox.dispatch_ingest(args)
######################################################
