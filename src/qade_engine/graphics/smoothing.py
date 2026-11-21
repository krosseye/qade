# SPDX-License-Identifier: GPL-3.0-or-later
"""Smooth motion between fixed steps."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QRectF


def interpolate(start: Any, end: Any, amount: float) -> Any:
    """Interpolates two values of the same kind.

    Handles numbers, ``QPointF``, ``QSizeF`` and ``QRectF``, tuples of any of
    these, and anything with a ``lerp(other, amount)`` method such as ``Pose``.
    Angles blend the straight way, so 350 to 10 degrees turns the long way round.
    """
    if isinstance(start, tuple):
        return tuple(interpolate(a, b, amount) for a, b in zip(start, end, strict=True))
    if isinstance(start, QRectF):
        return QRectF(
            interpolate(start.topLeft(), end.topLeft(), amount),
            interpolate(start.size(), end.size(), amount),
        )
    if hasattr(start, "lerp"):
        return start.lerp(end, amount)
    return start + (end - start) * amount


class Smoothed:
    """A value drawn blended between its last two steps.

    Gameplay reads ``value`` and changes it with ``set``; drawing uses ``at``.
    Only the first ``set`` in a step keeps where the value was, and a value
    nothing set this step draws still, so pushes and stops never jitter.

    Example:
        ```python
        def reset(self):
            self.ship = self.smoothed(QPointF(400, 300))

        def step_playing(self, dt):
            self.ship.set(self.ship.value + self.velocity * dt)

        def draw_world(self, frame):
            draw_ship(frame.painter, self.ship.at(frame.alpha))
        ```
    """

    __slots__ = ("_moved", "_previous", "_ticks", "_value")

    def __init__(self, value: Any, ticks: Callable[[], int]):
        """Starts still at a value.

        Args:
            value: Where it starts.
            ticks: Counts the fixed steps run so far, such as
                ``ArcadeGame.tick_count``. ``ArcadeGame.smoothed`` passes it.
        """
        self._ticks = ticks
        self._value = self._previous = value
        self._moved = ticks()

    @property
    def value(self) -> Any:
        """Where it is as of the last step."""
        return self._value

    def set(self, value: Any) -> None:
        """Moves it, to be drawn sliding there from where it was last step."""
        tick = self._ticks()
        if tick != self._moved:
            self._previous, self._moved = self._value, tick
        self._value = value

    def jump(self, value: Any) -> None:
        """Moves it without sliding, for teleports and respawns."""
        self._value = self._previous = value
        self._moved = self._ticks()

    def at(self, alpha: float) -> Any:
        """Where to draw it.

        Args:
            alpha: ``Frame.alpha``: how far into the next step this frame is.

        Returns:
            The value blended from last step's, or just the value if
            nothing moved it in the latest step.
        """
        if self._moved != self._ticks():
            return self._value
        return interpolate(self._previous, self._value, alpha)
