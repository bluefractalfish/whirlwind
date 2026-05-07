"""whirlwind.operators.stitch

PURPOSE:
    - stitch many georeferenced tile GeoTIFFs into one mosaic GeoTIFF

BEHAVIOR:
    - discover tile .tif files under an input directory
    - write a GDAL tile list file
    - run gdalbuildvrt
    - run gdal_translate from VRT to GeoTIFF

PUBLIC:
    - StitchRequest
    - StitchResult
    - stitch_tiles
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from whirlwind.domain.filesystem.runtree import RunTree


@dataclass(frozen=True)
class Request:
    run_tree: RunTree 
    shard_dirs: Iterable[Path]
    pattern: str = "**/*.tif"
    overwrite: bool = True
    bigtiff: bool = True
    tiled: bool = True
    compress: str | None = None


@dataclass(frozen=True)
class Result:
     tiles_seen: int
    list_path: Path
    vrt_path: Path
    out_tif: Path


class StitchTifBridge: 
    ... 

def iter_tile_tifs(input_dir: Path, pattern: str = "**/*.tif") -> Iterable[Path]:
    """
    Yield tile GeoTIFFs in deterministic order.
    """
    yield from sorted(p for p in input_dir.glob(pattern) if p.is_file())


def write_tile_list(paths: Iterable[Path], list_path: Path) -> int:
    """
    Write GDAL-compatible input list.

    gdalbuildvrt supports:
        -input_file_list list.txt

    This avoids creating a huge command line for many tiles.
    """
    list_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with list_path.open("w", encoding="utf-8") as f:
        for path in paths:
            f.write(str(path.resolve()))
            f.write("\n")
            n += 1

    return n


def run_checked(cmd: list[str]) -> None:
    """
    Run a command and raise a useful error if it fails.
    """
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "command failed\n"
            f"cmd: {' '.join(cmd)}\n"
            f"returncode: {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def build_vrt(
    *,
    tile_list: Path,
    vrt_path: Path,
    overwrite: bool = True,
) -> None:
    """
    Run gdalbuildvrt using a file list.
    """
    vrt_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["gdalbuildvrt"]

    if overwrite:
        cmd.append("-overwrite")

    cmd.extend(
        [
            "-input_file_list",
            str(tile_list),
            str(vrt_path),
        ]
    )

    run_checked(cmd)


def translate_vrt_to_tif(
    *,
    vrt_path: Path,
    out_tif: Path,
    overwrite: bool = True,
    bigtiff: bool = True,
    tiled: bool = True,
    compress: str | None = None,
) -> None:
    """
    Run gdal_translate from VRT to final GeoTIFF.
    """
    out_tif.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["gdal_translate"]

    if overwrite:
        # gdal_translate supports -overwrite in modern GDAL.
        cmd.append("-overwrite")

    cmd.extend(["-of", "GTiff"])

    if tiled:
        cmd.extend(["-co", "TILED=YES"])

    if bigtiff:
        cmd.extend(["-co", "BIGTIFF=YES"])

    if compress is not None:
        cmd.extend(["-co", f"COMPRESS={compress}"])

    cmd.extend(
        [
            str(vrt_path),
            str(out_tif),
        ]
    )

    run_checked(cmd)


def stitch_tiles(req: StitchRequest) -> StitchResult:
    """
    Build VRT and translate it into a full GeoTIFF.

    Memory behavior:
        - does not load tile arrays into Python
        - GDAL places tiles by georeferencing
        - suitable for large tile sets
    """
    input_dir = req.input_dir.expanduser().resolve()
    vrt_path = req.vrt_path.expanduser().resolve()
    out_tif = req.out_tif.expanduser().resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"input directory does not exist: {input_dir}")

    list_path = vrt_path.with_suffix(".tiles.txt")

    tiles_seen = write_tile_list(
        iter_tile_tifs(input_dir, req.pattern),
        list_path,
    )

    if tiles_seen == 0:
        raise ValueError(f"no tile GeoTIFFs found under {input_dir} with pattern {req.pattern}")

    build_vrt(
        tile_list=list_path,
        vrt_path=vrt_path,
        overwrite=req.overwrite,
    )

    translate_vrt_to_tif(
        vrt_path=vrt_path,
        out_tif=out_tif,
        overwrite=req.overwrite,
        bigtiff=req.bigtiff,
        tiled=req.tiled,
        compress=req.compress,
    )

    return StitchResult(
        tiles_seen=tiles_seen,
        list_path=list_path,
        vrt_path=vrt_path,
        out_tif=out_tif,
    )
