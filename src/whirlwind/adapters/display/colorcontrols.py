
import numpy as np 
from rasterio.enums import ColorInterp
from rasterio.io import DatasetWriter 

def blend_rgb_overlay(
    base_rgb: np.ndarray,
    overlay_rgb: np.ndarray,
    *,
    alpha: float,
) -> np.ndarray:

    if base_rgb.shape != overlay_rgb.shape:
        raise ValueError(
            f"overlay shape mismatch: base={base_rgb.shape}, overlay={overlay_rgb.shape}"
        )

    alpha = float(np.clip(alpha, 0.0, 1.0))

    blended = (
        base_rgb.astype(np.float32) * (1.0 - alpha)
        + overlay_rgb.astype(np.float32) * alpha
    )

    return np.clip(blended, 0, 255).astype(np.uint8)

def interpret_colors(dst: DatasetWriter, arr: np.ndarray) -> None:
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


def to_rgb(
    arr: np.ndarray,
    *,
    display_bands: tuple[int, int, int] | None = None,
    p_low: float,
    p_high: float,
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
        gray = stretch_to_uint8(arr[:1], p_low=p_low, p_high=p_high)
        return np.repeat(gray, 3, axis=0)

    if display_bands is None:
        display_bands = (0, 1, 2)

    max_index = arr.shape[0] - 1
    for b in display_bands:
        if b < 0 or b > max_index:
            raise ValueError(f"display band index {b} out of range for array with {arr.shape[0]} bands")

    rgb = arr[list(display_bands)]
    return stretch_to_uint8(rgb, p_low=p_low, p_high=p_high)


def to_rgba(
    arr: np.ndarray,
    *,
    display_bands: tuple[int, int, int] | None = None,
    alpha_band: int,
    p_low: float,
    p_high: float,
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

    rgb = to_rgb(
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

def stretch_to_uint8(
    arr: np.ndarray,
    *,
    p_low: float,
    p_high: float,
    ) -> np.ndarray:
    """
    Percentile-stretch an array to uint8.

    Input:
        (bands, height, width)

    Output:
        uint8 array with same shape

    Notes:
        - any constant nonzero bands become 255.
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
            out[band_index].fill(band_to_uint8(vals))
            continue

        scaled = (band - lo) * 255.0 / (hi - lo)
        scaled = np.clip(scaled, 0.0, 255.0)

        out[band_index] = scaled.astype(np.uint8)

    return out


def band_to_uint8(vals: np.ndarray) -> int:
    """
    choose a visible value for a constant display band.

    for constant alpha, this is not used. alpha is handled separately.
    """
    if vals.size == 0:
        return 0

    v = float(vals[0])
    if not np.isfinite(v):
        return 0

    if v <= 0:
        return 0

    return 255


