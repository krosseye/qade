# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawn over the view: the crystal as it charges, the threat vignette, and
the lines of text that tell you how things stand."""

from math import cos, pi, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QLinearGradient,
    QPainter,
    QPen,
)

from qade_engine.graphics import (
    RED,
    WHITE,
    YELLOW,
    blend,
    current_theme,
    draw_centered,
    make_font,
    with_alpha,
)

from ..bear import Bear
from ..config import NEAR_DISTANCE

BANNER_TIME = 2.0  # "LEVEL N" shows this long at the start of a level


def draw_attunement(
    painter: QPainter,
    width: float,
    height: float,
    charge: float,
    angle: float,
    flash: float,
) -> None:
    """The exit crystal up close, as you stand on it and charge it
    (``charge`` 0 to 1).

    As it fills, it swells, grows facets (four to eight), and its light
    floods the view; ``flash`` (1 at each tick of the charge, fading to 0)
    makes it pulse with the ticking. A ring round it shows the charge.
    ``angle`` is the crystal's spin, in radians.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    glow = charge**1.5 * (0.5 + 0.5 * flash)
    painter.fillRect(QRectF(0, 0, width, height), with_alpha(YELLOW, int(70 * glow)))

    cx, cy = width / 2, height / 2
    size = height * (0.08 + 0.04 * charge + 0.01 * flash)
    sides = min(8, 4 + int(charge * 5))

    def point(radius: float, rise: float, turn: float) -> QPointF:
        x, z = radius * cos(turn), radius * sin(turn)
        return QPointF(cx + x * size, cy - (rise - 0.3 * z) * size)

    ring = [point(1.0, 0.0, angle + 2 * pi * k / sides) for k in range(sides)]
    top, bottom = point(0.0, 1.5, 0.0), point(0.0, -1.5, 0.0)
    edges = [(top, p) for p in ring] + [(bottom, p) for p in ring]
    edges += [(ring[k], ring[(k + 1) % sides]) for k in range(sides)]

    color = blend(YELLOW, WHITE, 0.7 * flash * charge)
    for pen in (
        QPen(with_alpha(color, int(60 + 60 * flash)), 6),
        QPen(color, 1.8),
    ):
        painter.setPen(pen)
        for start, end in edges:
            painter.drawLine(start, end)

    if charge > 0:
        radius = size * 2.2
        box = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
        painter.setPen(QPen(with_alpha(YELLOW, 50), 2))
        painter.drawEllipse(box)
        painter.setPen(QPen(color, 3))
        painter.drawArc(box, 90 * 16, -int(charge * 360 * 16))
    painter.restore()


def draw_vignette(
    painter: QPainter,
    width: float,
    height: float,
    amount: float,
    side: int | None = None,
) -> None:
    """A red glow at the view's edges, ``amount`` from 0 to 1.

    With ``side`` (0 ahead, 1 right, 2 behind, 3 left, relative to the view)
    the glow gathers on that edge: ahead at the top, behind at the bottom.
    """
    if amount <= 0:
        return
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    band = height * 0.12
    frame = amount if side is None else amount * 0.5
    for index in range(6):
        alpha = int(40 * frame * (1 - index / 6))
        inset = band * index / 6
        painter.setPen(QPen(with_alpha(RED, alpha), band / 6))
        painter.drawRect(QRectF(inset, inset, width - 2 * inset, height - 2 * inset))

    if side is not None:
        depth = height * 0.3
        edge, inner, rect = {
            0: (QPointF(0, 0), QPointF(0, depth), QRectF(0, 0, width, depth)),
            1: (
                QPointF(width, 0),
                QPointF(width - depth, 0),
                QRectF(width - depth, 0, depth, height),
            ),
            2: (
                QPointF(0, height),
                QPointF(0, height - depth),
                QRectF(0, height - depth, width, depth),
            ),
            3: (QPointF(0, 0), QPointF(depth, 0), QRectF(0, 0, depth, height)),
        }[side % 4]
        glow = QLinearGradient(edge, inner)
        glow.setColorAt(0.0, with_alpha(RED, int(150 * amount)))
        glow.setColorAt(1.0, with_alpha(RED, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(rect, glow)
    painter.restore()


def draw_status(
    painter: QPainter, width: float, height: float, now: float, bear: Bear
) -> None:
    """A line at the bottom on what the bear is doing; blinks when it is close."""
    theme = current_theme()
    if not bear.awake:
        text, color = "IT LIES IN WAIT", theme.text_muted
    elif not bear.hunting:
        text, color = "IT PROWLS THE TUNNELS", theme.text
    elif bear.path_distance > NEAR_DISTANCE:
        text, color = "IT HAS YOUR SCENT", theme.warning
    else:
        if int(now * 4) % 2:
            return  # blink
        text, color = "RUN! IT IS CLOSE", theme.danger
    make_font(painter, 12, spacing=3)
    painter.setPen(QPen(color))
    draw_centered(painter, text, width, height - 30)


def draw_crystal_prompt(
    painter: QPainter,
    width: float,
    height: float,
    now: float,
    attuning: bool,
    charge: float,
) -> None:
    """On the crystal: how to charge it, or how far along it is."""
    theme = current_theme()
    if attuning:
        text = f"ATTUNING  {int(charge * 100):3d}%"
        color = theme.highlight
    else:
        text, color = "[HOLD] TO ATTUNE", theme.accent
        if int(now * 2) % 2:
            color = with_alpha(color, 120)
    make_font(painter, 14, spacing=4)
    painter.setPen(QPen(color))
    draw_centered(painter, text, width, height * 0.8)


def draw_banner(
    painter: QPainter, width: float, height: float, level: int, level_time: float
) -> None:
    """Show "LEVEL N" for the first ``BANNER_TIME`` seconds, fading out."""
    if level_time > BANNER_TIME:
        return
    fade = min(1.0, (BANNER_TIME - level_time) / 0.5)
    make_font(painter, 22, spacing=8)
    painter.setPen(QPen(with_alpha(current_theme().highlight, int(255 * fade))))
    draw_centered(painter, f"LEVEL {level:02d}", width, height * 0.3)
