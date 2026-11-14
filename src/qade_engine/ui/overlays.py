# SPDX-License-Identifier: GPL-3.0-or-later
"""Terminal-style screens: the standby signal and the typewriter intro."""

from collections.abc import Sequence

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPen, QTextLayout

from qade_engine.graphics.palette import Opacity, with_alpha
from qade_engine.graphics.primitives import draw_centered
from qade_engine.graphics.theme import current_theme, make_font
from qade_engine.graphics.viewport import Viewport

from .panels import draw_terminal_frame

TERMINAL_MAX_WIDTH: float = 650.0
STANDBY_MAX_HEIGHT: float = 200.0
INTRO_MAX_HEIGHT: float = 420.0

CHARS_PER_SECOND: int = 20


def _centered_panel(
    viewport: Viewport, max_width: float, max_height: float
) -> tuple[float, float, float, float]:
    """(x, y, width, height) of a panel centred in the view, with a margin."""
    width = min(max_width, viewport.width - 40.0)
    height = min(max_height, viewport.height - 60.0)
    return (
        (viewport.width - width) / 2.0,
        (viewport.height - height) / 2.0,
        width,
        height,
    )


def draw_standby(
    painter: QPainter,
    viewport: Viewport,
    current_time: float,
    title: str,
    message: str,
    prompt: str,
) -> None:
    """Draws the standby screen, waiting for a key.

    Args:
        painter: The painter to draw with.
        viewport: The view.
        current_time: Wall-clock seconds, to blink the prompt.
        title: The terminal header.
        message: The centred message.
        prompt: The blinking "press a key" prompt.
    """
    theme = current_theme()
    painter.save()

    panel_x, panel_y, panel_width, panel_height = _centered_panel(
        viewport, TERMINAL_MAX_WIDTH, STANDBY_MAX_HEIGHT
    )
    header_height = draw_terminal_frame(
        painter, panel_x, panel_y, panel_width, panel_height, title
    )

    make_font(painter, 14)
    painter.setPen(QPen(theme.text))
    draw_centered(painter, message, viewport.width, panel_y + header_height + 55)

    if int(current_time) % 2 == 0:
        make_font(painter, 11)
        painter.setPen(QPen(theme.highlight))
        draw_centered(painter, prompt, viewport.width, panel_y + panel_height - 35)

    painter.restore()


def draw_intro(
    painter: QPainter,
    viewport: Viewport,
    intro_state,
    current_time: float,
    title: str,
    prompt: str,
    highlights: Sequence[str] = (),
) -> None:
    """Draws the intro, typing out each line as the narration reaches it.

    Args:
        painter: The painter to draw with.
        viewport: The view.
        intro_state: The ``IntroSequencer`` saying which lines show and when
            each started.
        current_time: Wall-clock seconds, on the same clock as the
            sequencer's start times.
        title: The terminal header.
        prompt: The "press a key" prompt at the bottom.
        highlights: Lines containing any of these are drawn in red.
    """
    theme = current_theme()
    painter.save()

    panel_x, panel_y, panel_width, panel_height = _centered_panel(
        viewport, TERMINAL_MAX_WIDTH, INTRO_MAX_HEIGHT
    )
    header_height = draw_terminal_frame(
        painter, panel_x, panel_y, panel_width, panel_height, title
    )

    _draw_typewriter_lines(
        painter,
        viewport,
        intro_state,
        current_time,
        highlights,
        panel_x=panel_x,
        start_y=panel_y + header_height + 25.0,
        max_text_width=int(panel_width - 40.0),
    )

    divider_y = panel_y + panel_height - 45.0
    painter.setPen(QPen(with_alpha(theme.accent, Opacity.SUBTLE), 1.0))
    painter.drawLine(
        QPointF(panel_x + 20.0, divider_y),
        QPointF(panel_x + panel_width - 20.0, divider_y),
    )

    make_font(painter, 11)
    painter.setPen(QPen(theme.highlight))
    draw_centered(painter, prompt, viewport.width, panel_y + panel_height - 18.0)

    painter.restore()


def _draw_typewriter_lines(
    painter: QPainter,
    viewport: Viewport,
    intro_state,
    current_time: float,
    highlights: Sequence[str],
    panel_x: float,
    start_y: float,
    max_text_width: int,
) -> None:
    """Draws the shown lines, wrapped, each revealed a character at a time."""
    theme = current_theme()
    body_font = make_font(painter, 12)
    line_height = painter.fontMetrics().height() + 6

    lines = intro_state.displayed_lines
    cursor_visible = int(current_time * 3) % 2 == 0
    current_y = start_y

    for index, text in enumerate(lines):
        started_time = intro_state.line_start_times.get(index, current_time)
        visible_characters = min(
            int((current_time - started_time) * CHARS_PER_SECOND), len(text)
        )
        if visible_characters <= 0:
            continue

        is_critical = any(word in text for word in highlights)
        painter.setPen(QPen(theme.danger if is_critical else theme.text))

        display_text = text[:visible_characters]
        if (
            index == len(lines) - 1
            and visible_characters < len(text)
            and cursor_visible
        ):
            display_text += "█"

        layout = QTextLayout(display_text, body_font)
        layout.beginLayout()
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max_text_width)
            x_coordinate = max(
                (viewport.width - line.naturalTextWidth()) / 2.0, panel_x + 20.0
            )
            line.draw(painter, QPointF(x_coordinate, current_y))
            current_y += line_height
        layout.endLayout()
