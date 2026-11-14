# SPDX-License-Identifier: GPL-3.0-or-later
"""A play area that can take the shape of the window."""


class PlayField:
    """Where a game happens, in canvas units. Starts as the canvas.

    ``ArcadeGame`` keeps one the shape of the window for a ``FILL_WINDOW``
    game. Entities can share it, so a resize reaches them all.

    Attributes:
        width: Current width.
        height: Current height.
    """

    def __init__(self, width: float, height: float) -> None:
        """Creates a field the size of the canvas.

        Args:
            width: Canvas width.
            height: Canvas height.
        """
        self.width, self.height = width, height
        self._canvas_width, self._canvas_height = width, height

    @property
    def width_scale(self) -> float:
        """The field's width relative to the canvas's."""
        return self.width / self._canvas_width

    @property
    def area_scale(self) -> float:
        """The field's area relative to the canvas's.

        Scale the number of hazards by this, and a run is just as crowded on
        any screen.
        """
        return self.width_scale * self.height / self._canvas_height
