"""whirlwind.io.shard_exports

PURPOSE:
    - read tile shard tar files
    - reconstruct npy/json tile pairs
    - export tiles as GeoTIFFs for visual inspection or raw inspection

BEHAVIOR:
    - stream one shard tar at a time
    - pair {key}.npy with {key}.json
    - write one GeoTIFF per tile
    - display mode writes safe QGIS-readable RGB/RGBA uint8 tiles
    - raw mode preserves all bands and original dtype

PUBLIC:
    - ExportMode
    - DisplayKind
    - ShardExportStats
    - iter_encoded_pairs
    - load_npy_tile
    - write_tile_tif
    - shard_to_tifs
    - shard_dir_to_tifs
    - inspect_one_tile
"""

from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

import numpy as np
import rasterio
from rasterio import Affine
from rasterio.enums import ColorInterp


ExportMode = Literal["display", "raw"]
DisplayKind = Literal["rgb", "rgba"]


@dataclass(frozen=True)
class ShardExportStats:
    """Summary returned by shard export operations."""

    shards_seen: int = 0
    tiles_seen: int = 0
    tiles_written: int = 0
    errors: int = 0


def list_to_affine(v: list[float] | tuple[float, ...]) -> Affine:
    """
    Rebuild rasterio Affine from metadata transform list.

    Expected:
        [a, b, c, d, e, f]
    """
    if len(v) != 6:
        raise ValueError(f"expected transform with 6 values, got {len(v)}")

    return Affine(v[0], v[1], v[2], v[3], v[4], v[5])


def iter_encoded_pairs(shard_path: Path | str) -> Iterator[tuple[str, bytes, dict[str, Any]]]:
    """
    Stream npy/json pairs from one shard tar.

    Expected current shard format from ShardWriter.write():

        {tile.key}.npy
        {tile.key}.json

    Yields:
        (key, npy_bytes, metadata_dict)
    """
    shard_path = Path(shard_path)

    npy_by_key: dict[str, bytes] = {}
    json_by_key: dict[str, dict[str, Any]] = {}

    with tarfile.open(shard_path, "r") as tar:
        for member in tar:
            if not member.isfile():
                continue

            member_path = Path(member.name)
            suffix = member_path.suffix.lower()

            if suffix not in {".npy", ".json"}:
                continue

            key = member_path.stem

            f = tar.extractfile(member)
            if f is None:
                continue

            payload = f.read()

            if suffix == ".npy":
                npy_by_key[key] = payload

            elif suffix == ".json":
                json_by_key[key] = json.loads(payload.decode("utf-8"))

            if key in npy_by_key and key in json_by_key:
                yield key, npy_by_key.pop(key), json_by_key.pop(key)


def load_npy_tile(payload: bytes) -> np.ndarray:
    """
    Load one tile tensor from npy bytes.

    Expected normal shape:
        (bands, height, width)

    Also accepts:
        (height, width)

    Returns:
        array with shape (bands, height, width)
    """
    arr = np.load(io.BytesIO(payload), allow_pickle=False)

    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    return arr


def _constant_band_to_uint8(vals: np.ndarray) -> int:
    """
    Choose a visible value for a constant display band.

    For constant alpha, this is not used. Alpha is handled separately.
    """
    if vals.size == 0:
        return 0

    v = float(vals[0])
    if not np.isfinite(v):
        return 0

    if v <= 0:
        return 0

    return 255


def stretch_to_uint8(
    arr: np.ndarray,
    *,
    p_low: float = 2.0,
    p_high: float = 98.0,
) -> np.ndarray:
    """
    Percentile-stretch an array to uint8.

    Input:
        (bands, height, width)

    Output:
        uint8 array with same shape

    Notes:
        - Constant nonzero bands become 255.
        - Constant zero bands remain 0.
        - Invalid-only bands remain 0.
    """
    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    out = np.zeros(arr.shape, dtype=np.uint8)

    for band_index in range(arr.shape[0]):
        band = arr[band_index].astype(np.float32, copy=False)

        finite = np.isfinite(band)
        if not finite.any():
            continue

        vals = band[finite]

        lo = float(np.percentile(vals, p_low))
        hi = float(np.percentile(vals, p_high))

        if not np.isfinite(lo) or not np.isfinite(hi):
            continue

        if hi <= lo:
            out[band_index].fill(_constant_band_to_uint8(vals))
            continue

        scaled = (band - lo) * 255.0 / (hi - lo)
        scaled = np.clip(scaled, 0.0, 255.0)

        out[band_index] = scaled.astype(np.uint8)

    return out


def make_display_rgb(
    arr: np.ndarray,
    *,
    display_bands: tuple[int, int, int] | None = None,
    p_low: float = 2.0,
    p_high: float = 98.0,
) -> np.ndarray:
    """
    Create a 3-band RGB display tile.

    This is the safest QGIS display output.

    Default:
        first three bands -> RGB

    Example display_bands:
        (0, 1, 2) = RGB
        (2, 1, 0) = BGR to RGB
        (3, 0, 1) = false color if band 4 is NIR
    """
    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    if arr.shape[0] < 3:
        return stretch_to_uint8(arr, p_low=p_low, p_high=p_high)

    if display_bands is None:
        display_bands = (0, 1, 2)

    max_index = arr.shape[0] - 1
    for b in display_bands:
        if b < 0 or b > max_index:
            raise ValueError(f"display band index {b} out of range for array with {arr.shape[0]} bands")

    rgb = arr[list(display_bands)]
    return stretch_to_uint8(rgb, p_low=p_low, p_high=p_high)


def make_display_rgba(
    arr: np.ndarray,
    *,
    display_bands: tuple[int, int, int] | None = None,
    alpha_band: int = 3,
    p_low: float = 2.0,
    p_high: float = 98.0,
) -> np.ndarray:
    """
    Create a 4-band RGBA display tile.

    Critical behavior:
        - RGB bands are stretched.
        - Alpha band is preserved/clipped.
        - Alpha is NOT percentile-stretched.

    This prevents the bug where constant alpha=255 becomes alpha=0.
    """
    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    if arr.shape[0] < 4:
        raise ValueError("RGBA display requires at least 4 source bands")

    if alpha_band < 0 or alpha_band >= arr.shape[0]:
        raise ValueError(f"alpha band index {alpha_band} out of range for array with {arr.shape[0]} bands")

    rgb = make_display_rgb(
        arr,
        display_bands=display_bands,
        p_low=p_low,
        p_high=p_high,
    )

    alpha = arr[alpha_band]

    if alpha.dtype == np.uint8:
        alpha_u8 = alpha.copy()
    else:
        alpha_u8 = np.clip(alpha, 0, 255).astype(np.uint8)

    # If alpha is constant positive, force fully opaque.
    # This handles alpha=255 and also alpha=1 style masks.
    finite = np.isfinite(alpha_u8)
    if finite.any():
        vals = alpha_u8[finite]
        if vals.size > 0 and vals.min() == vals.max() and vals.max() > 0:
            alpha_u8.fill(255)

    return np.concatenate([rgb, alpha_u8[np.newaxis, :, :]], axis=0)


def _profile_from_array_and_metadata(
    arr: np.ndarray,
    metadata: dict[str, Any],
    *,
    compress: str | None = None,
) -> dict[str, Any]:
    """
    Build a rasterio GeoTIFF profile from tile array and metadata.

    Important:
        No nodata is set here. Display TIFFs should not use nodata,
        especially when writing RGB/RGBA for QGIS inspection.
    """
    count, height, width = arr.shape

    transform_values = metadata.get("transform")
    if transform_values is None:
        tile_id = metadata.get("tile_id", "<unknown>")
        raise ValueError(f"tile metadata missing transform: {tile_id}")

    profile: dict[str, Any] = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": count,
        "dtype": arr.dtype,
        "crs": metadata.get("crs") or None,
        "transform": list_to_affine(transform_values),
    }

    if compress is not None:
        profile["compress"] = compress

    # Internal tiling helps QGIS/GDAL for normal 256/512 tiles.
    # Avoid invalid block sizes for very small edge tiles.
    if width >= 16 and height >= 16:
        profile["tiled"] = True
        profile["blockxsize"] = min(256, width)
        profile["blockysize"] = min(256, height)

    # Defensive: never propagate nodata into display outputs.
    profile.pop("nodata", None)

    return profile


def _set_color_interpretation(dst: rasterio.io.DatasetWriter, arr: np.ndarray) -> None:
    """
    Set color interpretation for QGIS/GDAL display.

    1 band  -> gray
    3 bands -> RGB
    4 bands -> RGBA
    other   -> undefined
    """
    count = arr.shape[0]

    if count == 1:
        dst.colorinterp = (ColorInterp.gray,)

    elif count == 3:
        dst.colorinterp = (
            ColorInterp.red,
            ColorInterp.green,
            ColorInterp.blue,
        )

    elif count == 4:
        dst.colorinterp = (
            ColorInterp.red,
            ColorInterp.green,
            ColorInterp.blue,
            ColorInterp.alpha,
        )

    else:
        dst.colorinterp = tuple(ColorInterp.undefined for _ in range(count))


def write_tile_tif(
    arr: np.ndarray,
    metadata: dict[str, Any],
    out_path: Path | str,
    *,
    mode: ExportMode = "display",
    display_kind: DisplayKind = "rgb",
    display_bands: tuple[int, int, int] | None = None,
    alpha_band: int = 3,
    p_low: float = 2.0,
    p_high: float = 98.0,
    compress: str | None = None,
) -> None:
    """
    Write one tile npy/json pair as a GeoTIFF.

    Args:
        arr:
            Tile array. Expected shape is (bands, height, width).

        metadata:
            Tile metadata decoded from {key}.json.

        out_path:
            Destination .tif path.

        mode:
            "display":
                Write QGIS-friendly uint8 display TIFF.

            "raw":
                Preserve array dtype and values.

        display_kind:
            Used only when mode="display".

            "rgb":
                Write 3-band RGB. Safest option for QGIS.

            "rgba":
                Write 4-band RGBA. Preserves alpha band instead of stretching it.

        display_bands:
            Zero-based RGB source bands.

            Examples:
                (0, 1, 2) -> RGB
                (2, 1, 0) -> BGR to RGB
                (3, 0, 1) -> false color

        alpha_band:
            Zero-based alpha source band for display_kind="rgba".

        p_low / p_high:
            Percentile stretch range for RGB bands.

        compress:
            None means no compression.
            Examples: "deflate", "lzw".
    """
    out_path = Path(out_path)

    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    if mode == "display":
        if display_kind == "rgb":
            arr = make_display_rgb(
                arr,
                display_bands=display_bands,
                p_low=p_low,
                p_high=p_high,
            )

        elif display_kind == "rgba":
            arr = make_display_rgba(
                arr,
                display_bands=display_bands,
                alpha_band=alpha_band,
                p_low=p_low,
                p_high=p_high,
            )

        else:
            raise ValueError(f"unknown display kind: {display_kind}")

    elif mode == "raw":
        # Preserve all bands and original dtype.
        pass

    else:
        raise ValueError(f"unknown export mode: {mode}")

    profile = _profile_from_array_and_metadata(
        arr,
        metadata,
        compress=compress,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr)
        _set_color_interpretation(dst, arr)


def tile_output_path(
    out_dir: Path,
    key: str,
    metadata: dict[str, Any],
) -> Path:
    """
    Build output path for one tile.

    Prefers metadata["tile_id"], falls back to shard key.
    """
    tile_id = metadata.get("tile_id") or key
    return out_dir / f"{tile_id}.tif"


def shard_to_tifs(
    shard_path: Path | str,
    out_dir: Path | str,
    *,
    mode: ExportMode = "display",
    display_kind: DisplayKind = "rgb",
    display_bands: tuple[int, int, int] | None = None,
    alpha_band: int = 3,
    p_low: float = 2.0,
    p_high: float = 98.0,
    compress: str | None = None,
    stop_on_error: bool = False,
) -> ShardExportStats:
    """
    Convert one shard tar into individual GeoTIFF tiles.

    Memory behavior:
        loads one npy/json tile pair at a time.
    """
    shard_path = Path(shard_path)
    out_dir = Path(out_dir)

    tiles_seen = 0
    tiles_written = 0
    errors = 0

    for key, npy_bytes, metadata in iter_encoded_pairs(shard_path):
        tiles_seen += 1

        try:
            arr = load_npy_tile(npy_bytes)
            out_path = tile_output_path(out_dir, key, metadata)

            write_tile_tif(
                arr,
                metadata,
                out_path,
                mode=mode,
                display_kind=display_kind,
                display_bands=display_bands,
                alpha_band=alpha_band,
                p_low=p_low,
                p_high=p_high,
                compress=compress,
            )

            tiles_written += 1

        except Exception:
            errors += 1
            if stop_on_error:
                raise

    return ShardExportStats(
        shards_seen=1,
        tiles_seen=tiles_seen,
        tiles_written=tiles_written,
        errors=errors,
    )


def shard_dir_to_tifs(
    shard_dir: Path | str,
    out_dir: Path | str,
    *,
    pattern: str = "*.tar",
    mode: ExportMode = "display",
    display_kind: DisplayKind = "rgb",
    display_bands: tuple[int, int, int] | None = None,
    alpha_band: int = 3,
    grouped: bool = True,
    p_low: float = 2.0,
    p_high: float = 98.0,
    compress: str | None = None,
    stop_on_error: bool = False,
) -> ShardExportStats:
    """
    Convert a directory of shard tar files into GeoTIFF tiles.

    Args:
        shard_dir:
            Directory containing shard tar files.

        out_dir:
            Destination directory.

        pattern:
            Shard glob. Default: "*.tar"

        mode:
            "display" for visual TIFFs.
            "raw" for exact npy values.

        display_kind:
            "rgb" is safest for QGIS.
            "rgba" preserves alpha band.

        display_bands:
            Zero-based RGB source bands.

        alpha_band:
            Zero-based alpha source band for RGBA display.

        grouped:
            If True:
                writes to out_dir / shard_name / tile_id.tif

            If False:
                writes to out_dir / tile_id.tif

        p_low / p_high:
            Percentile stretch range for display RGB bands.

        compress:
            None writes uncompressed GeoTIFFs.

        stop_on_error:
            If True, raise on first failed tile.
            If False, count errors and continue.
    """
    shard_dir = Path(shard_dir)
    out_dir = Path(out_dir)

    shards_seen = 0
    tiles_seen = 0
    tiles_written = 0
    errors = 0

    for shard_path in sorted(shard_dir.glob(pattern)):
        if not shard_path.is_file():
            continue

        shards_seen += 1

        this_out_dir = out_dir / shard_path.stem if grouped else out_dir

        stats = shard_to_tifs(
            shard_path,
            this_out_dir,
            mode=mode,
            display_kind=display_kind,
            display_bands=display_bands,
            alpha_band=alpha_band,
            p_low=p_low,
            p_high=p_high,
            compress=compress,
            stop_on_error=stop_on_error,
        )

        tiles_seen += stats.tiles_seen
        tiles_written += stats.tiles_written
        errors += stats.errors

    return ShardExportStats(
        shards_seen=shards_seen,
        tiles_seen=tiles_seen,
        tiles_written=tiles_written,
        errors=errors,
    )


def inspect_array(arr: np.ndarray) -> list[dict[str, Any]]:
    """
    Return per-band stats for an in-memory tile array.
    """
    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    out: list[dict[str, Any]] = []

    for index in range(arr.shape[0]):
        band = arr[index]
        finite = np.isfinite(band)

        if not finite.any():
            out.append(
                {
                    "band": index + 1,
                    "valid": False,
                }
            )
            continue

        vals = band[finite]

        out.append(
            {
                "band": index + 1,
                "valid": True,
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
                "mean": float(np.mean(vals)),
                "p2": float(np.percentile(vals, 2)),
                "p98": float(np.percentile(vals, 98)),
                "unique_sample": np.unique(vals[:1000]).tolist()[:20],
            }
        )

    return out


def inspect_one_tile(shard_path: Path | str) -> dict[str, Any]:
    """
    Inspect the first tile in a shard.

    Useful when exports are all white, all black, transparent,
    or QGIS reports no valid pixels.
    """
    for key, npy_bytes, metadata in iter_encoded_pairs(shard_path):
        arr = load_npy_tile(npy_bytes)

        return {
            "key": key,
            "tile_id": metadata.get("tile_id"),
            "shape": tuple(arr.shape),
            "dtype": str(arr.dtype),
            "metadata_dtype": metadata.get("dtype"),
            "crs": metadata.get("crs"),
            "has_transform": metadata.get("transform") is not None,
            "band_stats": inspect_array(arr),
        }

    raise ValueError(f"no npy/json tile pairs found in shard: {shard_path}")


def inspect_written_tif(path: Path | str) -> dict[str, Any]:
    """
    Inspect one written GeoTIFF for nodata/mask/colorinterp problems.

    Use this when QGIS says:
        no valid pixels found in sampling
    """
    path = Path(path)

    with rasterio.open(path) as ds:
        arr = ds.read(masked=True)

        bands: list[dict[str, Any]] = []

        for index in range(arr.shape[0]):
            band = arr[index]
            mask = np.ma.getmaskarray(band)
            all_masked = bool(mask.all())

            record: dict[str, Any] = {
                "band": index + 1,
                "all_masked": all_masked,
            }

            if not all_masked:
                vals = band.compressed()
                record.update(
                    {
                        "min": float(vals.min()),
                        "max": float(vals.max()),
                        "mean": float(vals.mean()),
                    }
                )

            bands.append(record)

        return {
            "path": str(path),
            "count": ds.count,
            "dtype": tuple(ds.dtypes),
            "nodata": ds.nodata,
            "nodatavals": ds.nodatavals,
            "colorinterp": tuple(str(c) for c in ds.colorinterp),
            "mask_flags": tuple(tuple(str(flag) for flag in flags) for flags in ds.mask_flag_enums),
            "bands": bands,
        }
