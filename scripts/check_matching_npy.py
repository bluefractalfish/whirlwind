#!/usr/bin/env python3
"""Find .npy files that contain identical NumPy arrays."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


CHUNK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class ArrayInfo:
    path: Path
    shape: tuple[int, ...]
    dtype: str
    digest: str


def dtype_identity(dtype: np.dtype) -> str:
    """Return a stable dtype description, including structured fields."""
    if dtype.fields is not None:
        return repr(dtype.descr)
    return dtype.str


def array_byte_chunks(
    array: np.ndarray,
    chunk_bytes: int = CHUNK_BYTES,
) -> Iterator[memoryview]:
    """Yield array data in C-index order without copying the whole array."""
    itemsize = max(1, array.dtype.itemsize)
    buffer_items = max(1, chunk_bytes // itemsize)

    iterator = np.nditer(
        array,
        flags=["external_loop", "buffered", "zerosize_ok"],
        op_flags=["readonly"],
        order="C",
        buffersize=buffer_items,
    )

    for values in iterator:
        contiguous = np.ascontiguousarray(values)
        yield memoryview(contiguous).cast("B")


def inspect_array(path: Path) -> ArrayInfo:
    """Load one NPY safely and hash its array identity and contents."""
    array = np.load(path, mmap_mode="r", allow_pickle=False)

    if array.dtype.hasobject:
        raise ValueError("object arrays are not supported")

    dtype = dtype_identity(array.dtype)
    digest = hashlib.sha256()
    digest.update(repr(tuple(array.shape)).encode("utf-8"))
    digest.update(b"\0")
    digest.update(dtype.encode("utf-8"))
    digest.update(b"\0")

    for chunk in array_byte_chunks(array):
        digest.update(chunk)

    return ArrayInfo(
        path=path,
        shape=tuple(int(value) for value in array.shape),
        dtype=dtype,
        digest=digest.hexdigest(),
    )


def find_npy_files(directory: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.npy" if recursive else "*.npy"
    return sorted(
        path
        for path in directory.glob(pattern)
        if path.is_file()
    )


def relative_name(path: Path, directory: Path) -> str:
    try:
        return str(path.relative_to(directory))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find .npy files containing exactly identical arrays. "
            "NPY headers are ignored; shape, dtype, and array data must match."
        )
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="directory to scan (default: current directory)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="scan subdirectories recursively",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON",
    )
    parser.add_argument(
        "--fail-on-duplicates",
        action="store_true",
        help="exit with status 1 when duplicate arrays are found",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="hide per-file progress messages",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    directory = args.directory.expanduser().resolve()

    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2

    paths = find_npy_files(directory, args.recursive)
    groups: dict[tuple[tuple[int, ...], str, str], list[ArrayInfo]] = (
        defaultdict(list)
    )
    errors: list[dict[str, str]] = []

    for index, path in enumerate(paths, start=1):
        if not args.quiet and not args.json:
            print(
                f"[{index}/{len(paths)}] {relative_name(path, directory)}",
                file=sys.stderr,
            )

        try:
            info = inspect_array(path)
        except Exception as error:
            errors.append(
                {
                    "path": relative_name(path, directory),
                    "error": str(error),
                }
            )
            continue

        key = (info.shape, info.dtype, info.digest)
        groups[key].append(info)

    duplicate_groups = [
        group
        for group in groups.values()
        if len(group) > 1
    ]
    duplicate_groups.sort(
        key=lambda group: relative_name(group[0].path, directory)
    )

    if args.json:
        result = {
            "directory": str(directory),
            "files_found": len(paths),
            "files_checked": sum(len(group) for group in groups.values()),
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_file_count": sum(
                len(group) for group in duplicate_groups
            ),
            "groups": [
                {
                    "shape": list(group[0].shape),
                    "dtype": group[0].dtype,
                    "sha256": group[0].digest,
                    "files": [
                        relative_name(info.path, directory)
                        for info in group
                    ],
                }
                for group in duplicate_groups
            ],
            "errors": errors,
        }
        print(json.dumps(result, indent=2))
    else:
        if duplicate_groups:
            print(
                f"\nFound {len(duplicate_groups)} identical array group(s):"
            )

            for number, group in enumerate(duplicate_groups, start=1):
                first = group[0]
                print(
                    f"\nGroup {number}: shape={first.shape}, "
                    f"dtype={first.dtype}"
                )
                print(f"  SHA-256: {first.digest}")
                for info in group:
                    print(f"  {relative_name(info.path, directory)}")
        else:
            print("\nNo identical arrays found.")

        print(
            f"\nScanned {len(paths)} file(s); "
            f"checked {sum(len(group) for group in groups.values())}."
        )

        if errors:
            print(f"Skipped {len(errors)} unreadable file(s):", file=sys.stderr)
            for error in errors:
                print(
                    f"  {error['path']}: {error['error']}",
                    file=sys.stderr,
                )

    if args.fail_on_duplicates and duplicate_groups:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
