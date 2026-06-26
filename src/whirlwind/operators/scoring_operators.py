

from math import exp

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def gaussian_distance_score(distance: float | None, sigma: float) -> float:
    """
    Smooth distance decay.

    distance = 0       -> 1.0
    distance = sigma   -> ~0.367
    distance = 2*sigma -> ~0.018
    """
    if distance is None:
        return 0.0

    if sigma <= 0:
        return 0.0

    d = max(0.0, float(distance))
    return clamp01(exp(-((d / sigma) ** 2)))


def noisy_or(*weighted_scores: float) -> float:
    """
    Combine positive evidence without letting the sum exceed 1.0.

    This is useful because multiple weak signals should compound:

        near path + near area + debris-looking

    without requiring one signal to dominate.
    """
    p_not = 1.0

    for score in weighted_scores:
        s = clamp01(score)
        p_not *= 1.0 - s

    return clamp01(1.0 - p_not)
