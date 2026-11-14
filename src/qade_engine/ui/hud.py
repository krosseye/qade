# SPDX-License-Identifier: GPL-3.0-or-later
"""The standard HUD, and the pause and game-over screens."""

from collections.abc import Sequence

from PySide6.QtGui import QColor, QPainter, QPen

from qade_engine.graphics.palette import Opacity, with_alpha
from qade_engine.graphics.primitives import draw_centered
from qade_engine.graphics.theme import Theme, current_theme, make_font
from qade_engine.graphics.viewport import Viewport
from qade_engine.perf import PerfStats

from .panels import HudRow, draw_hud_panel

HUD_MARGIN: int = 15
GAME_PANEL_WIDTH: int = 180
SYSTEMS_PANEL_WIDTH: int = 200


def format_clock(seconds: float) -> str:
    """Formats seconds as MM:SS.

    Args:
        seconds: The time.

    Returns:
        The time as minutes and seconds, such as ``"01:05"``.
    """
    whole = int(seconds)
    return f"{whole // 60:02d}:{whole % 60:02d}"


def health_color(theme: Theme, value: float, target: float) -> QColor:
    """Picks a status colour for a measurement against its target.

    Args:
        theme: The theme supplying status colours.
        value: The measurement.
        target: Its target. 0 or less always counts as healthy.

    Returns:
        Success at 95% of target or more, warning at 75% or more, else danger.
    """
    if target <= 0:
        return theme.success
    ratio = value / target
    if ratio >= 0.95:
        return theme.success
    if ratio >= 0.75:
        return theme.warning
    return theme.danger


def draw_hud(
    painter: QPainter,
    viewport: Viewport,
    rows: Sequence[HudRow],
    performance_metrics: PerfStats,
    title: str = "PLAYER",
) -> None:
    """Draws the game's panel at top left and the systems panel at top right.

    Args:
        painter: The painter to draw with.
        viewport: The view.
        rows: The game's readouts, such as score and time.
        performance_metrics: Frame and update rates.
        title: Header of the game's panel.
    """
    theme = current_theme()
    draw_hud_panel(painter, HUD_MARGIN, HUD_MARGIN, GAME_PANEL_WIDTH, title, list(rows))

    systems_rows = [
        HudRow(
            "FPS",
            f"{performance_metrics.fps:03.0f}",
            health_color(
                theme, performance_metrics.fps, performance_metrics.target_fps
            ),
        ),
    ]
    if performance_metrics.show_details:
        systems_rows += [
            HudRow(
                "FRAME",
                f"{performance_metrics.frame_ms:4.1f}/{performance_metrics.worst_ms:4.1f}ms",
                theme.text_muted,
            ),
            HudRow(
                "UPS",
                f"{performance_metrics.ups:03.0f}",
                health_color(
                    theme, performance_metrics.ups, performance_metrics.target_ups
                ),
            ),
            HudRow("PAINT", f"{performance_metrics.paint_ms:4.1f}ms", theme.text_muted),
        ]
    draw_hud_panel(
        painter,
        viewport.width - HUD_MARGIN - SYSTEMS_PANEL_WIDTH,
        HUD_MARGIN,
        SYSTEMS_PANEL_WIDTH,
        "SYSTEMS",
        systems_rows,
    )


def _draw_banner(
    painter: QPainter,
    viewport: Viewport,
    title: str,
    title_color: QColor,
    prompt: str,
) -> None:
    """A dark screen over the view, a big centred title, and a prompt under it."""
    theme = current_theme()
    painter.fillRect(
        0,
        0,
        int(viewport.width),
        int(viewport.height),
        with_alpha(theme.surface, Opacity.MEDIUM),
    )
    center_y = viewport.height / 2

    make_font(painter, 26)
    painter.setPen(QPen(title_color))
    draw_centered(painter, title, viewport.width, center_y - 20)

    make_font(painter, 12)
    painter.setPen(QPen(theme.text_muted))
    draw_centered(painter, prompt, viewport.width, center_y + 30)


def draw_paused(painter: QPainter, viewport: Viewport, title: str, prompt: str) -> None:
    """Draws the pause screen over the frozen world.

    Args:
        painter: The painter to draw with.
        viewport: The view.
        title: The headline, such as ``"PAUSED"``.
        prompt: How to resume.
    """
    painter.save()
    _draw_banner(painter, viewport, title, current_theme().highlight, prompt)
    painter.restore()


def draw_game_over(
    painter: QPainter,
    viewport: Viewport,
    title: str,
    prompt: str,
    score: int,
    high_score: int,
    is_new_high_score: bool,
) -> None:
    """Draws the game-over screen: a headline, a retry prompt and the score.

    Args:
        painter: The painter to draw with.
        viewport: The view.
        title: The headline, such as ``"GAME OVER"``.
        prompt: The retry prompt.
        score: This run's score.
        high_score: The best score so far.
        is_new_high_score: Whether this run set the high score.
    """
    theme = current_theme()
    painter.save()
    _draw_banner(painter, viewport, title, theme.danger, prompt)
    center_y = viewport.height / 2

    if is_new_high_score:
        score_text = f"NEW HIGH SCORE: {high_score:06d}"
        score_color = theme.highlight
    else:
        score_text = f"SCORE {score:06d}   BEST {high_score:06d}"
        score_color = theme.accent

    make_font(painter, 14)
    painter.setPen(QPen(score_color))
    draw_centered(painter, score_text, viewport.width, center_y + 70)

    painter.restore()
