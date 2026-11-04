"""Sample-aware uncertainty reporting for human-labeled retrieval benchmarks.

Wilson's score interval describes binary Hit@K on these evaluated cases.
It is NOT calibration of retrieval scores, nor a guarantee of population
performance when an operator chose a non-random dataset.
"""

from math import sqrt

_WILSON_Z_95 = 1.959963984540054


def wilson_hit_rate_95(*, successes: int, trials: int) -> tuple[float, float]:
    """Return the fixed 95% Wilson score interval, inclusive in [0, 1]."""
    if (
        isinstance(successes, bool)
        or isinstance(trials, bool)
        or not isinstance(successes, int)
        or not isinstance(trials, int)
        or trials < 1
        or successes < 0
        or successes > trials
    ):
        raise ValueError("hit rate interval requires valid count data")
    p = successes / trials
    z2 = _WILSON_Z_95**2
    denominator = 1 + z2 / trials
    center = (p + z2 / (2 * trials)) / denominator
    half_width = (
        _WILSON_Z_95 * sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials)) / denominator
    )
    # Avoid roundoff like 6.9e-18 when the observed rate is exactly zero.
    lower = 0.0 if successes == 0 else max(0.0, center - half_width)
    upper = 1.0 if successes == trials else min(1.0, center + half_width)
    return lower, upper
