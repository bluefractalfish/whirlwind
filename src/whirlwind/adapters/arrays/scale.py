import numpy as np 

def scale_to_uint8(arr: np.ndarray, *, p_low: float, p_high: float) -> np.ndarray:
    x = np.asarray(arr)

    if x.dtype == np.uint8:
        return x.copy()

    x = x.astype(np.float32)
    out = np.zeros(x.shape, dtype=np.uint8)

    for c in range(x.shape[-1]):
        band = x[..., c]
        finite = np.isfinite(band)

        if not finite.any():
            continue

        vals = band[finite]
        raw_min = float(vals.min())
        raw_max = float(vals.max())

        if raw_max <= raw_min:
            out[..., c].fill(255 if raw_max > 0 else 0)
            continue

        lo = float(np.percentile(vals, p_low))
        hi = float(np.percentile(vals, p_high))

        if hi <= lo:
            lo = raw_min
            hi = raw_max

        y = (band - lo) / (hi - lo)
        y = np.clip(y, 0.0, 1.0)
        y[~finite] = 0.0

        out[..., c] = (y * 255.0).round().astype(np.uint8)

    return out


