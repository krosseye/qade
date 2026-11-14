# SPDX-License-Identifier: GPL-3.0-or-later
"""Small drawing helpers shared by games and the interface."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen


def hairline(color: QColor) -> QPen:
    """A 1-pixel pen, whatever the painter's scale.

    Qt strokes these on a fast path, several times quicker than any wider pen,
    so prefer it wherever a thin line will do.

    Args:
        color: The pen's colour.

    Returns:
        The pen.
    """
    pen = QPen(color, 1.0)
    pen.setCosmetic(True)
    return pen


def draw_corner_brackets(
    painter: QPainter,
    position_x: float,
    position_y: float,
    width: float,
    height: float,
    bracket_size: float,
    bracket_color: QColor,
    thickness: float = 2.0,
) -> None:
    """Draws a bracket at each corner of a rectangle.

    Args:
        painter: The painter to draw with.
        position_x: The rectangle's left edge.
        position_y: The rectangle's top edge.
        width: The rectangle's width.
        height: The rectangle's height.
        bracket_size: Length of each bracket arm.
        bracket_color: The brackets' colour.
        thickness: Pen width.
    """
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(bracket_color, thickness))
    for corner_x, direction_x in ((position_x, 1), (position_x + width, -1)):
        for corner_y, direction_y in ((position_y, 1), (position_y + height, -1)):
            painter.drawLine(
                QPointF(corner_x, corner_y),
                QPointF(corner_x + direction_x * bracket_size, corner_y),
            )
            painter.drawLine(
                QPointF(corner_x, corner_y),
                QPointF(corner_x, corner_y + direction_y * bracket_size),
            )


def draw_centered(
    painter: QPainter, text: str, total_width: float, baseline_y: float
) -> None:
    """Draws one line of text centred horizontally, in the painter's font and pen.

    Args:
        painter: The painter to draw with.
        text: The text.
        total_width: Width to centre within, starting at x = 0.
        baseline_y: The text's baseline.
    """
    text_width = painter.fontMetrics().horizontalAdvance(text)
    painter.drawText(int(total_width // 2 - text_width // 2), int(baseline_y), text)
