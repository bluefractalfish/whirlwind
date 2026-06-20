
from dataclasses import dataclass
from typing import Any 

import numpy as np 

from whirlwind.domain.tile import Tile


@dataclass(frozen=True)
class SkipDecision:
    skip: bool
    reason: str
    stats: dict[str, float]

    @classmethod
    def keep(cls, stats: dict[str, float]) -> "SkipDecision":
        return cls(skip=False, reason="keep", stats=stats)

    @classmethod
    def reject(cls, reason: str, stats: dict[str, float]) -> "SkipDecision":
        return cls(skip=True, reason=reason, stats=stats)


def should_skip_tile(
    tile: Tile,
    *,
    min_content_fraction: float,
    max_black_fraction: float = 0.75,
    max_white_fraction: float = 0.75,
    min_global_std: float = 2.0,
    min_channel_std_mean: float = 1.5,
    zero_is_empty: bool = True,
) -> SkipDecision:
    """
    Return skip=True only for unusable visual tiles.

    This is not semantic classification.
    It only rejects tiles that are empty, mostly black, mostly white,
    mostly nodata/collar, or too flat to be useful.

    Expected rasterio array shape: (bands, height, width).
    """

    if tile.read is None:
        return SkipDecision.reject(
            "missing_tile_read",
            {
                "content_fraction": 0.0,
                "black_fraction": 1.0,
                "white_fraction": 0.0,
                "valid_fraction": 0.0,
                "global_std": 0.0,
                "channel_std_mean": 0.0,
            },
        )

    arr = tile.read.array

    if arr.ndim == 2:
        rgb = arr[np.newaxis, :, :]
    elif arr.ndim == 3:
        # Only use RGB-like bands for skip decisions.
        # This prevents alpha/NIR from making black RGB pixels look valid.
        rgb = arr[: min(3, arr.shape[0])]
    else:
        raise ValueError(f"expected tile array with 2 or 3 dims, got {arr.shape}")

    if np.ma.isMaskedArray(rgb):
        mask = np.ma.getmaskarray(rgb)
        data = np.ma.filled(rgb, 0)
        valid_by_band = ~mask
    else:
        data = np.asarray(rgb)
        valid_by_band = np.isfinite(data)

    data = np.nan_to_num(
        data.astype("float32", copy=False),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    if data.size == 0:
        return SkipDecision.reject(
            "empty_array",
            {
                "content_fraction": 0.0,
                "black_fraction": 1.0,
                "white_fraction": 0.0,
                "valid_fraction": 0.0,
                "global_std": 0.0,
                "channel_std_mean": 0.0,
            },
        )

    # Require all checked display bands to be valid.
    # np.all is stricter than np.any and avoids one valid alpha/NIR-like band
    # keeping otherwise empty RGB pixels.
    valid_pixel = np.all(valid_by_band, axis=0)

    observed_max = float(np.nanmax(data)) if data.size else 0.0

    # Choose thresholds based on the actual numeric range.
    # This avoids the bug where float 0..1 imagery gets treated as black
    # because eps=2.0 is too large.
    if observed_max <= 1.5:
        black_threshold = 0.02
        white_threshold = 0.98
        std_scale = 255.0
    elif observed_max <= 255.0:
        black_threshold = 5.0
        white_threshold = 250.0
        std_scale = 1.0
    else:
        # uint16-like or high dynamic range.
        # Use observed range instead of dtype max because some uint16 rasters
        # have useful data far below 65535.
        black_threshold = observed_max * (5.0 / 255.0)
        white_threshold = observed_max * (250.0 / 255.0)
        std_scale = 255.0 / max(observed_max, 1.0)

    black_pixel = np.all(data <= black_threshold, axis=0)
    white_pixel = np.all(data >= white_threshold, axis=0)

    if zero_is_empty:
        content_pixel = valid_pixel & ~black_pixel & ~white_pixel
    else:
        content_pixel = valid_pixel & ~white_pixel

    total = int(content_pixel.size)

    if total == 0:
        return SkipDecision.reject(
            "zero_pixels",
            {
                "content_fraction": 0.0,
                "black_fraction": 1.0,
                "white_fraction": 0.0,
                "valid_fraction": 0.0,
                "global_std": 0.0,
                "channel_std_mean": 0.0,
            },
        )

    content_fraction = float(content_pixel.sum() / total)
    black_fraction = float(black_pixel.sum() / total)
    white_fraction = float(white_pixel.sum() / total)
    valid_fraction = float(valid_pixel.sum() / total)

    channel_stds = [
        float(np.std(data[i]) * std_scale)
        for i in range(data.shape[0])
    ]

    channel_std_mean = float(np.mean(channel_stds))
    global_std = float(np.std(data) * std_scale)

    stats = {
        "content_fraction": content_fraction,
        "black_fraction": black_fraction,
        "white_fraction": white_fraction,
        "valid_fraction": valid_fraction,
        "global_std": global_std,
        "channel_std_mean": channel_std_mean,
    }

    if valid_fraction <= 0.05:
        return SkipDecision.reject("mostly_invalid", stats)

    if content_fraction < min_content_fraction:
        return SkipDecision.reject("low_content", stats)

    if black_fraction > max_black_fraction:
        return SkipDecision.reject("mostly_black", stats)

    if white_fraction > max_white_fraction:
        return SkipDecision.reject("mostly_white", stats)

    if global_std < min_global_std:
        return SkipDecision.reject("too_flat_global", stats)

    if channel_std_mean < min_channel_std_mean:
        return SkipDecision.reject("too_flat_channels", stats)

    return SkipDecision.keep(stats)

@dataclass(frozen=True)
class TileContentStats:
    valid_fraction: float
    nonzero_fraction: float
    content_fraction: float
    black_fraction: float
    white_fraction: float
    mostly_empty: bool

    def record(self) -> dict[str, Any]:
        return {
            "valid_fraction": self.valid_fraction,
            "nonzero_fraction": self.nonzero_fraction,
            "content_fraction": self.content_fraction,
            "black_fraction": self.black_fraction,
            "white_fraction": self.white_fraction,
            "mostly_empty": self.mostly_empty,
        }


def tile_content_stats(
    tile,
    *,
    min_content_fraction: float,
    zero_is_empty: bool = True,
    eps: float = 2.0,
    white_eps: float = 2.0,
    max_black_fraction: float = 0.40,
    max_white_fraction: float = 0.40,
) -> TileContentStats:
    """
    Decide whether a tile has enough real RGB image content.

    - Only checks RGB-like bands, not alpha/NIR.
    - Treats near-black and near-white padding as empty.
    - Prevents black collars / white collars from being classified as water.
    """

    if tile.read is None:
        return TileContentStats(
            valid_fraction=0.0,
            nonzero_fraction=0.0,
            content_fraction=0.0,
            black_fraction=1.0,
            white_fraction=0.0,
            mostly_empty=True,
        )

    arr = tile.read.array

    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(
            f"expected tile array shape (bands, height, width), got {arr.shape}"
        )

    # Use only first three image bands for content detection.
    # This avoids alpha=255 or NIR values making black RGB pixels look valid.
    rgb = arr[: min(3, arr.shape[0])]

    if np.ma.isMaskedArray(rgb):
        mask = np.ma.getmaskarray(rgb)
        data = np.ma.filled(rgb, 0)
        valid_by_band = ~mask
    else:
        data = np.asarray(rgb)
        valid_by_band = np.isfinite(data)

    # Require all RGB bands to be valid, not just one band.
    valid_pixel = np.all(valid_by_band, axis=0)

    safe = np.nan_to_num(data.astype("float32"), nan=0.0, posinf=0.0, neginf=0.0)

    # Near-black means all RGB bands are close to zero.
    black_pixel = np.all(np.abs(safe) <= eps, axis=0)

    # Infer likely max value.
    # uint8 -> 255, uint16 -> 65535, float normalized -> 1.0
    if np.issubdtype(data.dtype, np.integer):
        dtype_max = float(np.iinfo(data.dtype).max)
    else:
        observed_max = float(np.nanmax(safe)) if safe.size else 1.0
        dtype_max = 1.0 if observed_max <= 1.5 else 255.0

    white_threshold = dtype_max - white_eps

    # Near-white means all RGB bands are close to dtype max.
    white_pixel = np.all(safe >= white_threshold, axis=0)

    if zero_is_empty:
        nonzero_pixel = ~black_pixel
    else:
        nonzero_pixel = valid_pixel

    # Real content excludes black padding and white padding.
    content_pixel = valid_pixel & nonzero_pixel & ~white_pixel

    total_pixels = int(content_pixel.size)

    if total_pixels == 0:
        return TileContentStats(
            valid_fraction=0.0,
            nonzero_fraction=0.0,
            content_fraction=0.0,
            black_fraction=1.0,
            white_fraction=0.0,
            mostly_empty=True,
        )

    valid_fraction = float(valid_pixel.sum() / total_pixels)
    nonzero_fraction = float(nonzero_pixel.sum() / total_pixels)
    content_fraction = float(content_pixel.sum() / total_pixels)
    black_fraction = float(black_pixel.sum() / total_pixels)
    white_fraction = float(white_pixel.sum() / total_pixels)

    mostly_empty = (
        content_fraction < min_content_fraction
        or black_fraction > max_black_fraction
        or white_fraction > max_white_fraction
    )

    return TileContentStats(
        valid_fraction=valid_fraction,
        nonzero_fraction=nonzero_fraction,
        content_fraction=content_fraction,
        black_fraction=black_fraction,
        white_fraction=white_fraction,
        mostly_empty=mostly_empty,
    )


