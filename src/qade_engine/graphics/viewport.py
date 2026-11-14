# SPDX-License-Identifier: GPL-3.0-or-later
"""How an app's canvas maps onto the window."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Viewport:
    """A window measured in an app's canvas units, and the scale that gets it there.

    The canvas fits the window in its shorter direction, so this is at least
    the canvas size, and larger along the window's longer direction.

    Attributes:
        width: The window's width in canvas units.
        height: The window's height in canvas units.
        scale: Window pixels per canvas unit.
    """

    width: float
    height: float
    scale: float

    @classmethod
    def fit(cls, window: tuple[int, int], canvas: tuple[int, int]) -> "Viewport":
        """Fits a canvas to a window.

        Args:
            window: The window's size in pixels.
            canvas: The canvas's size.

        Returns:
            The viewport.
        """
        scale = max(min(window[0] / canvas[0], window[1] / canvas[1]), 0.1)
        return cls(window[0] / scale, window[1] / scale, scale)
