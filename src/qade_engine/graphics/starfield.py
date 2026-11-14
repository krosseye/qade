# SPDX-License-Identifier: GPL-3.0-or-later
"""A scrolling parallax starfield background."""

import random

from PySide6.QtCore import QRectF, Qt

from .palette import DARK_GREY, GREY, WHITE

COLORS = (GREY, DARK_GREY, WHITE)


class Star:
    """One star, placed at random.

    Attributes:
        x: Canvas x.
        y: Canvas y.
        size: Diameter in px.
        speed: Parallax factor: how much of the scroll velocity it moves by.
        color: One of ``COLORS``.
    """

    def __init__(self, width, height):
        """Places a star at random on a canvas.

        Args:
            width: Canvas width.
            height: Canvas height.
        """
        self.x = random.uniform(0, width)
        self.y = random.uniform(0, height)
        self.size = random.uniform(1, 4)
        self.speed = random.uniform(0.1, 0.5)
        self.color = random.choice(COLORS)

    def draw(self, painter, x, y):
        """Fills the star with the painter's brush.

        Args:
            painter: The painter to draw with.
            x: View x.
            y: View y.
        """
        painter.drawEllipse(QRectF(x - 0.5, y - 0.5, self.size + 1, self.size + 1))


class StarField:
    """A parallax background that wraps around a canvas.

    Attributes:
        width: Canvas width.
        height: Canvas height.
        stars: Every star.
    """

    def __init__(self, width: float, height: float, count: int = 200):
        """Scatters stars over a canvas.

        Args:
            width: Canvas width.
            height: Canvas height.
            count: Number of stars.
        """
        self.width = width
        self.height = height
        self.stars = [Star(width, height) for _ in range(count)]
        self._by_color = [
            (color, [star for star in self.stars if star.color is color])
            for color in COLORS
        ]
        self._velocity = (0.0, 0.0)

    def scroll(self, velocity_x, velocity_y, dt):
        """Scrolls every star by a world velocity times its own parallax speed.

        Every argument must be finite. A NaN or infinite one turns every star's
        position NaN, and wrapping can't bring them back, so the stars vanish
        until the field is rebuilt (``ArcadeGame`` rebuilds it each run).

        Args:
            velocity_x: Horizontal velocity in px/s.
            velocity_y: Vertical velocity in px/s.
            dt: Seconds to scroll for.
        """
        self._velocity = (velocity_x, velocity_y)
        for star in self.stars:
            star.x = (star.x + velocity_x * star.speed * dt) % self.width
            star.y = (star.y + velocity_y * star.speed * dt) % self.height

    def draw(self, painter, view_width, view_height, ahead=0.0):
        """Spreads the stars over the view. Each keeps its own size.

        Args:
            painter: The painter to draw with.
            view_width: The view's width.
            view_height: The view's height.
            ahead: Seconds past the last scroll to move the stars on.
        """
        scale_x, scale_y = view_width / self.width, view_height / self.height
        velocity_x, velocity_y = self._velocity
        painter.setPen(Qt.PenStyle.NoPen)
        for color, stars in self._by_color:
            painter.setBrush(color)
            for star in stars:
                x = star.x + velocity_x * star.speed * ahead
                y = star.y + velocity_y * star.speed * ahead
                star.draw(painter, x * scale_x, y * scale_y)
