
from typing import List, Optional
import argparse
import sys
import yaml
#import toolbox from local directory
#from rich.console import Console
#from pathlib import Path
from . import toolbox

def dispatch(args: argparse.Namespace)->int:
    toolbox.init_gdal()
    # dispatch scan
    if args.cmd == "scan":
        toolbox.dispatch_scan(args)
    # dispatch ingest
    if args.cmd == "ingest":
        toolbox.dispatch_ingest(args)

def apply_config(parser, tiles_parser, argv=None):
    args, _ = parser.parse_known_args(argv)

    if not getattr(args, "config", None):
        return parser.parse_args(argv)

    with open(args.config) as f:
        cfg = yaml.safe_load(f) or {}

    if args.cmd == "ingest" and args.ingest_cmd == "tiles":
        tiles_parser.set_defaults(**cfg.get("tiles", {}))

    return parser.parse_args(argv)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="whirlwind")
    p.add_argument("--config", type=str, help="path to config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    # scan
    scan = sub.add_parser("scan", help="Scan a directory and summarize files")
    scan.add_argument("root", type=str, help="Root directory to scan")
    scan.add_argument("--top-n", type=int, default=500, help="Show top N largest files (0 disables)")
    # ingest
    ingest = sub.add_parser("ingest", help="ingestion workflow")
    ingest_sub = ingest.add_subparsers(dest="ingest_cmd", required=True)
    # tile ingestion
    tiles = ingest_sub.add_parser("tiles", help="tile whole mosaics into shards + manifest (v1)")
    tiles.add_argument("--input", type=str, default=None, help="directory or glob for GeoTIFFs")
    tiles.add_argument("--input-csv", type=str, default=None, help="scan metadata CSV with 'uri' column")
    tiles.add_argument("--out", type=str, default=None, help="output directory")

    tiles.add_argument("--tile-size", type=int, default=512)
    tiles.add_argument("--stride", type=int, default=None, help="default: tile-size (non-overlapping)")
    tiles.add_argument("--drop-partial", action="store_true", default=True)
    tiles.add_argument("--keep-partial", action="store_false", dest="drop_partial")

    tiles.add_argument("--shard-size", type=int, default=4096)
    tiles.add_argument("--shard-prefix", type=str, default="tiles")

    tiles.add_argument("--manifest", choices=["parquet", "csv", "none"], default="parquet")

    tiles.add_argument("--dtype", choices=["float32", "uint16", "uint8"], default="float32",
                       help="Output dtype. float32 keeps float output; with --scale it becomes normalized [0,1].")
    tiles.add_argument("--scale", choices=["none", "minmax", "percentile"], default="none",
                       help="Scaling strategy. If not 'none', scaling is applied even for float32 output.")
    tiles.add_argument("--p-low", type=float, default=0.5)
    tiles.add_argument("--p-high", type=float, default=99.5)
    tiles.add_argument("--stats", choices=["sample", "compute", "from-metadata"], default="sample",
                       help="v1: all modes treated as sample; compute/full-pass can be added later.")
    tiles.add_argument("--num-samples", type=int, default=2048,
                       help="Number of sampled windows used to estimate scaling bounds.")

    tiles.add_argument("--resume", action="store_true", default=False)

    return p, tiles

def main(argv: Optional[List[str]] = None) -> int:
    p, tiles_parser = build_parser()
    args = apply_config(p, tiles_parser, argv)

    if args.cmd == "ingest" and args.ingest_cmd == "tiles" and not args.out:
        p.error("ingest tiles requires --out or tiles.out in config")

    try:
        return dispatch(args)
    except KeyboardInterrupt:
        toolbox.log("13")
        sys.exit(130)

if __name__ == "__main__":
    raise SystemExit(main())

