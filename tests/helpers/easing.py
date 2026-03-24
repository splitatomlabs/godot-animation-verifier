"""Easing functions for synthetic test frame generation.

Each function maps t in [0, 1] to an output value.
"""

import math


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out: fast start, decelerating to rest at 1.0."""
    return 1.0 - (1.0 - t) ** 3


def trans_back(t: float, overshoot: float = 1.70158) -> float:
    """Back easing (overshoot to ~1.2 then settle to 1.0).

    Matches Godot's TRANS_BACK behaviour.
    """
    return 1.0 + (overshoot + 1.0) * (t - 1.0) ** 3 + overshoot * (t - 1.0) ** 2


def trans_elastic(t: float, amplitude: float = 1.0, period: float = 0.3) -> float:
    """Elastic ease-out with spring oscillation.

    Matches Godot's TRANS_ELASTIC behaviour.
    """
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0

    s = period / 4 if amplitude <= 1.0 else period / (2.0 * math.pi) * math.asin(1.0 / amplitude)
    return amplitude * 2.0 ** (-10.0 * t) * math.sin((t - s) * (2.0 * math.pi) / period) + 1.0
