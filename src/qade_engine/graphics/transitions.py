# SPDX-License-Identifier: GPL-3.0-or-later
"""Full-screen effects drawn while the state machine plays a transition."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter

from qade_engine.core.state_machine import Transition, TransitionStyle

from .palette import BLACK, with_alpha


def draw_transition(
    painter: QPainter, width: float, height: float, transition: Transition
) -> None:
    """Draws a transition over the whole view.

    Args:
        painter: The painter to draw with.
        width: The view's width.
        height: The view's height.
        transition: The transition playing.
    """
    match transition.style:
        case TransitionStyle.FADE:
            darkness = 1.0 - abs(2.0 * transition.progress - 1.0)
            painter.fillRect(
                QRectF(0, 0, width, height), with_alpha(BLACK, round(255 * darkness))
            )
