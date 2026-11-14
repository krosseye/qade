# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared panels: a terminal frame, and the HUD's readout panel."""

from collections.abc import Sequence
from typing import NamedTuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from qade_engine.graphics.palette import Opacity, with_alpha
from qade_engine.graphics.primitives import draw_corner_brackets
from qade_engine.graphics.theme import current_theme, make_font


class HudRow(NamedTuple):
    """One readout line in a HUD panel.

    Attributes:
        label: Shown on the left.
        value: Shown on the right.
        color: The value's colour.
    """

    label: str
    value: str
    color: QColor


def draw_terminal_frame(
    painter: QPainter,
    position_x: float,
    position_y: float,
    width: float,
    height: float,
    title: str,
) -> float:
    """Draws a terminal backdrop with corner brackets and a titled header bar.

    Args:
        painter: The painter to draw with.
        position_x: The frame's left edge.
        position_y: The frame's top edge.
        width: The frame's width.
        height: The frame's height.
        title: The header's title.

    Returns:
        The header's height, to lay out content below it.
    """
    theme = current_theme()

    painter.setBrush(with_alpha(theme.surface, Opacity.STRONG))
    painter.setPen(QPen(with_alpha(theme.accent, Opacity.MEDIUM), 1.5))
    painter.drawRoundedRect(QRectF(position_x, position_y, width, height), 6.0, 6.0)

    draw_corner_brackets(
        painter,
        position_x,
        position_y,
        width,
        height,
        12.0,
        with_alpha(theme.accent, Opacity.STRONG),
    )

    header_height = 30.0
    painter.fillRect(
        int(position_x + 2),
        int(position_y + 2),
        int(width - 4),
        int(header_height),
        with_alpha(theme.accent, Opacity.FAINT),
    )

    make_font(painter, 9)
    painter.setPen(QPen(with_alpha(theme.accent, Opacity.STRONG)))
    painter.drawText(int(position_x + 15), int(position_y + 20), title)

    return header_height


def hud_panel_height(row_count: int) -> int:
    """The height of a ``draw_hud_panel`` panel, to place it before drawing it.

    Args:
        row_count: Rows in the panel.

    Returns:
        Its height.
    """
    return 22 + 4 + row_count * 20 + 6


def draw_hud_panel(
    painter: QPainter,
    position_x: float,
    position_y: float,
    width: float,
    title: str,
    rows: Sequence[HudRow],
) -> float:
    """Draws a HUD panel: a header with a status lamp, then a row per readout.

    Args:
        painter: The painter to draw with.
        position_x: The panel's left edge.
        position_y: The panel's top edge.
        width: The panel's width.
        title: The header's title.
        rows: The readouts.

    Returns:
        The panel's height.
    """
    padding = 10
    header_height = 22
    row_height = 20
    position_x, position_y, width = int(position_x), int(position_y), int(width)
    total_height = hud_panel_height(len(rows))

    theme = current_theme()
    painter.save()

    painter.setBrush(with_alpha(theme.surface, Opacity.STRONG))
    painter.setPen(QPen(with_alpha(theme.accent, Opacity.MEDIUM), 1.5))
    painter.drawRoundedRect(position_x, position_y, width, total_height, 6, 6)

    painter.fillRect(
        position_x + 2,
        position_y + 2,
        width - 4,
        header_height - 2,
        with_alpha(theme.accent, Opacity.FAINT),
    )
    painter.setPen(QPen(with_alpha(theme.accent, Opacity.SUBTLE), 1.0))
    painter.drawLine(
        position_x + 6,
        position_y + header_height,
        position_x + width - 6,
        position_y + header_height,
    )

    make_font(painter, 8, spacing=1.5)
    title_color = with_alpha(theme.accent, Opacity.STRONG)
    painter.setPen(QPen(title_color))
    painter.drawText(position_x + padding, position_y + 15, title)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(title_color)
    painter.drawEllipse(
        QPointF(position_x + width - padding - 2, position_y + header_height / 2.0),
        2.5,
        2.5,
    )

    draw_corner_brackets(
        painter,
        position_x,
        position_y,
        width,
        total_height,
        8.0,
        with_alpha(theme.accent, Opacity.STRONG),
    )

    make_font(painter, 10)
    font_metrics = painter.fontMetrics()

    for index, (label, value, value_color) in enumerate(rows):
        baseline_y = position_y + header_height + 4 + index * row_height + 14

        painter.setPen(QPen(theme.text_muted))
        painter.drawText(position_x + padding, baseline_y, f"{label}:")

        painter.setPen(QPen(value_color))
        value_x = position_x + width - padding - font_metrics.horizontalAdvance(value)
        painter.drawText(value_x, baseline_y, value)

    painter.restore()
    return total_height
