"""
owns all ingestion logic

IngestCommand

InJester
"""

import argparse
import csv
import io
import json
import math
import os
import sys
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_bounds

from .base import Command
from ..utils import durs as du
from ..utils import rwriters as rwr
from ..utils import geo

# INGEST #############################################

class IngestCommand(Command):
    name = "ingest"

    def configure(self, subparsers: argparse._SubParsersAction) -> None:
        parser = subparsers.add_parser(self.name, help="Ingestion workflow",)
        ingest_subparsers = parser.add_subparsers(dest="ingest_cmd", required=True)
        # tile subcommand
        self._configure_tiles(ingest_subparsers)
        # shard subcommand etc

    def _configure_tiles(self, subparsers: argparse._SubParsersAction) -> None:
        
        tiles = subparsers.add_parser("tiles",
            help="Tile whole mosaics into shards + manifest",)

        self._add_io_args(tiles)
        self._add_tiling_args(tiles)
        self._add_shard_args(tiles)
        self._add_quantization_args(tiles)

    def _add_io_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--input",
            type=str,
            default=None,
            help="csv, directory or glob",
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
            default="csv",
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

    def run(self, args: argparse.Namespace) -> int:
        if args.ingest_cmd == "tiles":
            t = Tiler(args=args)
            t._tesselate()
            return 0
         
######################################################

@dataclass
class Tiler:
    def __init__(self,args):
        uris = list(rwr._iter_uris(args.input))
        out_dir = du._get_root_(args.out)
        stride = args.stride if args.stride is not None else args.tile_size
        self.tp = TParams(
                        uris=uris, 
                        out_dir=out_dir,
                        tile_size = args.tile_size,
                        stride = stride,
                        drop_partial=args.drop_partial,
                        shard_size=args.shard_size,
                        shard_prefix=args.shard_prefix,
                        manifest_kind=args.manifest,
                        )
        self.qp = QParams(dtype = args.dtype, 
                          scale=args.scale, 
                          p_low = args.p_low, 
                          p_high = args.p_high,
                          per_band = True, 
                          stats = args.stats, 
                          num_samples = args.num_samples,
                          )
    def _make_directories(self) -> dict[str, Path]:
        """constructor for directories """
        root = self.tp.out_dir
        dirs = {
                "root": root,
                "shards": root / "shards",
                "manifest": root / "manifest"
                }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    def _tesselate(self) -> None:
        dirs = self._make_directories()
        shards_dir = dirs["shards"]
        man_dir = dirs["manifest"]
        for uri in self.tp.uris:
            uri = uri.strip()
            if not uri:
                continue
            # cut mosaic with uri, write shards and return
            # mosaic_id, number of tiles seen (n), 
            # number written (w)
            # number of erros (e)
            # number of skipped (s)
            summary = geo.cut_mosaic(uri, 
                                     man_dir, 
                                     shards_dir, 
                                     self.qp, 
                                     self.tp)

            mid, n, w, e, s = summary

                    
# param classes 
@dataclass(frozen=True)
class TParams:
    """ tiling instance parameterization """
    uris: Iterator[str]
    out_dir: Path
    tile_size: int
    stride: int
    drop_partial: bool 
    shard_size: int
    shard_prefix: str
    manifest_kind: str
    

@dataclass(frozen=True)
class QParams:
    """ quantization parameters """
    dtype: str # "float32" | "uint16" | "uint8"
    scale: str= "none" # "none" | "minmax" | "percentile"
    p_low: float = 2
    p_high: float = 98
    per_band: bool = True 
    stats: str = "sample" # "sample"  | "compute" (compute = full pass; slower)
    num_samples: int = 2048 # number of sampled windows per band 



