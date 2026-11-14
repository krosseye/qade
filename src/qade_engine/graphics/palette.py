# SPDX-License-Identifier: GPL-3.0-or-later
"""The fixed colour palette, and helpers that derive new colours from it.

Game-world objects such as ships, particles and stars draw with these
colours directly. Interface code uses the roles in ``theme`` instead.

The palette colours are shared instances, so never mutate them: derive
variants with ``with_alpha`` and ``blend``, which return new colours.
"""

from enum import IntEnum

from PySide6.QtGui import QColor

BLACK: QColor = QColor(0, 0, 0)
DARK_GREY: QColor = QColor(53, 50, 48)
GREY: QColor = QColor(169, 169, 169)
WHITE: QColor = QColor(255, 255, 255)

RED: QColor = QColor(255, 50, 60)
ORANGE: QColor = QColor(255, 165, 0)
YELLOW: QColor = QColor(255, 215, 50)
GREEN: QColor = QColor(50, 255, 140)
CYAN: QColor = QColor(0, 220, 255)


class Opacity(IntEnum):
    """Standard alpha levels, used in place of ad-hoc values.

    Attributes:
        FAINT: Washes and tints behind content.
        SUBTLE: Dividers and rules.
        MEDIUM: Borders, scrims and translucent fills.
        STRONG: Titles, brackets and solid-looking surfaces.
    """

    FAINT = 40
    SUBTLE = 80
    MEDIUM = 140
    STRONG = 210


def with_alpha(color: QColor, alpha: int) -> QColor:
    """Copies a colour with a new alpha.

    Args:
        color: The source colour.
        alpha: The alpha, from 0 to 255, typically an ``Opacity`` level.

    Returns:
        A new colour.
    """
    result = QColor(color)
    result.setAlpha(alpha)
    return result


def blend(start: QColor, end: QColor, amount: float) -> QColor:
    """Interpolates linearly between two colours, alpha included.

    Args:
        start: The colour at ``amount == 0``.
        end: The colour at ``amount == 1``.
        amount: How far from ``start`` to ``end``, from 0 to 1.

    Returns:
        A new colour.
    """
    return QColor(
        round(start.red() + (end.red() - start.red()) * amount),
        round(start.green() + (end.green() - start.green()) * amount),
        round(start.blue() + (end.blue() - start.blue()) * amount),
        round(start.alpha() + (end.alpha() - start.alpha()) * amount),
    )
