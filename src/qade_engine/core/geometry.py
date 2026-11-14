# SPDX-License-Identifier: GPL-3.0-or-later
"""Small numeric helpers."""


def clamp(value, low, high):
    """Keeps a value within a range.

    Args:
        value: The value.
        low: The smallest allowed value.
        high: The largest allowed value.

    Returns:
        ``value``, moved into ``[low, high]`` if outside it.
    """
    return max(low, min(value, high))


def lerp(start: float, end: float, amount: float) -> float:
    """Interpolates linearly between two values.

    Args:
        start: The value at ``amount == 0``.
        end: The value at ``amount == 1``.
        amount: How far from ``start`` to ``end``.

    Returns:
        The point ``amount`` of the way from ``start`` to ``end``.
    """
    return start + (end - start) * amount


def dist_sq(ax, ay, bx, by):
    """Squared distance between two points, to compare against a squared radius.

    Args:
        ax: First point's x.
        ay: First point's y.
        bx: Second point's x.
        by: Second point's y.

    Returns:
        The squared distance.
    """
    dx, dy = ax - bx, ay - by
    return dx * dx + dy * dy
