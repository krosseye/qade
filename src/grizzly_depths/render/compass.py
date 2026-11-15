# SPDX-License-Identifier: GPL-3.0-or-later
"""The compass: A strip along the top of the view that shows the player's heading."""

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QPolygonF

from qade_engine.graphics import (
    Opacity,
    current_theme,
    draw_corner_brackets,
    make_font,
    with_alpha,
)

SPAN = 180.0
TICK_STEP = 15
HEADINGS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def draw_compass(
    painter: QPainter, center_x: float, top: float, width: float, yaw: float
) -> None:
    """Draw the strip centred on ``center_x``, from ``top`` down, for a view
    facing ``yaw`` degrees."""
    theme = current_theme()
    height = 30.0
    left = center_x - width / 2
    box = QRectF(left, top, width, height)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    painter.setBrush(with_alpha(theme.surface, Opacity.STRONG))
    painter.setPen(QPen(with_alpha(theme.accent, Opacity.MEDIUM), 1.5))
    painter.drawRoundedRect(box, 6, 6)
    draw_corner_brackets(
        painter, left, top, width, height, 6.0, with_alpha(theme.accent, Opacity.STRONG)
    )
    painter.setClipRect(box.adjusted(2, 2, -2, -2))

    def place(bearing: float) -> tuple[float, float] | None:
        """Where a world bearing sits on the strip, and how visible it is
        (1 in the middle, fading to 0 at the ends); None if off the strip."""
        offset = (bearing - yaw + 180) % 360 - 180
        reach = offset / (SPAN / 2)
        if abs(reach) > 1:
            return None
        return center_x + reach * (width / 2 - 8), 1 - reach**2

    baseline = top + height - 4
    for bearing in range(0, 360, TICK_STEP):
        spot = place(bearing)
        if spot is None or bearing % 45 == 0:
            continue
        x, fade = spot
        color = with_alpha(theme.accent, int(Opacity.STRONG * fade))
        painter.setPen(QPen(color, 1.2))
        painter.drawLine(QPointF(x, baseline - 5), QPointF(x, baseline))

    for index, name in enumerate(HEADINGS):
        spot = place(index * 45)
        if spot is None:
            continue
        x, fade = spot
        cardinal = len(name) == 1
        make_font(painter, 11 if cardinal else 8)
        metrics = painter.fontMetrics()
        color = theme.text if cardinal else theme.text_muted
        if name == "N":
            color = theme.danger
        painter.setPen(QPen(with_alpha(color, int(255 * fade))))
        painter.drawText(
            QPointF(
                x - metrics.horizontalAdvance(name) / 2,
                top + height / 2 + metrics.capHeight() / 2,
            ),
            name,
        )

    painter.setClipping(False)
    painter.setPen(QPen(theme.highlight, 1.0))
    painter.setBrush(theme.highlight)
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(center_x - 5, top),
                QPointF(center_x + 5, top),
                QPointF(center_x, top + 6),
            ]
        )
    )
    painter.drawLine(
        QPointF(center_x, top + height - 6), QPointF(center_x, top + height)
    )
    painter.restore()
