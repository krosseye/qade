# SPDX-License-Identifier: GPL-3.0-or-later
"""Cabinet artwork: the textures warped onto a cabinet's marquee, screen,
control panel and coin door."""

import random
from functools import cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap

from qade_engine.graphics import (
    CYAN,
    GREEN,
    ORANGE,
    RED,
    WHITE,
    YELLOW,
    make_font,
    with_alpha,
)

BODY = QColor(4, 10, 17)  # cabinet panels
WIRE = QColor(120, 170, 190)  # trim lines on the art


def stipple(color: QColor) -> QBrush:
    """The dotted fill the cabinets use instead of flat shading."""
    return QBrush(color, Qt.BrushStyle.Dense6Pattern)


def _painter(pixmap: QPixmap) -> QPainter:
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return painter


def _set_font(painter: QPainter, size: float, spacing: float = 0.0) -> None:
    """Set the font by pixel size; make_font takes points (3/4 of a pixel)."""
    make_font(painter, size * 3 / 4, spacing=spacing)


def _centered_text(painter: QPainter, x: float, baseline: float, text: str) -> None:
    width = painter.fontMetrics().horizontalAdvance(text)
    painter.drawText(QPointF(x - width / 2, baseline), text)


def _fitted_size(
    painter: QPainter, text: str, max_width: float, max_size: float, spacing: float
) -> float:
    """The largest pixel size up to ``max_size`` at which ``text`` fits."""
    size = max_size
    while size > 8:
        _set_font(painter, size, spacing)
        if painter.fontMetrics().horizontalAdvance(text) <= max_width:
            break
        size -= 2
    return size


@cache
def marquee(title: str, accent_name: str) -> QPixmap:
    accent = QColor(accent_name)
    width, height = 384, 150
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(3, 8, 14))
    painter = _painter(pixmap)
    painter.fillRect(0, 0, width, height, stipple(with_alpha(accent, 40)))
    for inset, alpha, pen_width in ((10, 220, 2), (15, 120, 1)):
        painter.setPen(QPen(with_alpha(accent, alpha), pen_width))
        painter.drawLine(8, inset, width - 8, inset)
        painter.drawLine(8, height - inset, width - 8, height - inset)

    text = title.upper()
    size = _fitted_size(painter, text, width - 56, 46, 3)
    baseline = height / 2 + size * 0.36
    painter.setPen(QPen(with_alpha(accent, 70)))
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        _centered_text(painter, width / 2 + dx, baseline + dy, text)
    painter.setPen(QPen(WHITE))
    _centered_text(painter, width / 2, baseline, text)
    painter.end()
    return pixmap


@cache
def screen(title: str, accent_name: str) -> QPixmap:
    width, height = 320, 240
    accent = QColor(accent_name)
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(2, 5, 9))
    painter = _painter(pixmap)
    rng = random.Random(title)

    painter.setPen(Qt.PenStyle.NoPen)
    for _ in range(70):
        painter.setBrush(with_alpha(WHITE, rng.randint(60, 220)))
        size = rng.choice((1.0, 1.0, 1.5, 2.0))
        painter.drawEllipse(
            QPointF(rng.uniform(0, width), rng.uniform(0, height * 0.6)), size, size
        )

    horizon = height * 0.62
    painter.setPen(QPen(with_alpha(accent, 150), 1.2))
    painter.drawLine(QPointF(0, horizon), QPointF(width, horizon))
    for index in range(-8, 9):
        painter.drawLine(
            QPointF(width / 2 + index * 6, horizon),
            QPointF(width / 2 + index * 60, height),
        )
    row = 4.0
    while horizon + row < height:
        painter.drawLine(QPointF(0, horizon + row), QPointF(width, horizon + row))
        row *= 1.6

    _set_font(painter, 22, 2)
    painter.setPen(QPen(accent))
    _centered_text(painter, width / 2, height * 0.32, title.upper())
    _set_font(painter, 12, 2)
    painter.setPen(QPen(YELLOW))
    _centered_text(painter, width / 2, height * 0.46, "PRESS START")
    painter.end()
    return pixmap


@cache
def control_panel(accent_name: str) -> QPixmap:
    accent = QColor(accent_name)
    width, height = 384, 130
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(5, 11, 18))
    painter = _painter(pixmap)
    painter.fillRect(0, 0, width, height, stipple(with_alpha(WIRE, 40)))
    painter.setPen(QPen(WIRE, 2))
    painter.drawRect(6, 6, width - 12, height - 12)

    stick_x, stick_y = width * 0.27, height * 0.5
    painter.setBrush(QColor(8, 16, 24))
    painter.setPen(QPen(WHITE, 2))
    painter.drawEllipse(QPointF(stick_x, stick_y), 24, 24)
    painter.setBrush(accent)
    painter.drawEllipse(QPointF(stick_x, stick_y - 2), 12, 12)

    for index, color in enumerate((GREEN, ORANGE, CYAN)):
        button_y = stick_y + (-6 if index == 1 else 5)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(width * 0.55 + index * 42, button_y), 13, 13)
    painter.setBrush(RED)
    painter.drawRect(QRectF(width * 0.86, height * 0.32, 18, 10))
    painter.setBrush(YELLOW)
    painter.drawRect(QRectF(width * 0.86, height * 0.58, 18, 10))
    painter.end()
    return pixmap


@cache
def coin_door(accent_name: str) -> QPixmap:
    accent = QColor(accent_name)
    width, height = 192, 168
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(4, 9, 15))
    painter = _painter(pixmap)
    painter.fillRect(0, 0, width, height, stipple(with_alpha(WIRE, 34)))
    painter.setPen(QPen(WIRE, 2))
    painter.drawRect(8, 8, width - 16, height - 16)

    for slot_x in (width * 0.30, width * 0.70):
        painter.setBrush(QColor(2, 5, 8))
        painter.setPen(QPen(WHITE, 2))
        painter.drawRoundedRect(QRectF(slot_x - 17, 43, 34, 59), 5, 5)
        painter.setBrush(ORANGE)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(slot_x - 8, 29, 16, 7))
        painter.setPen(QPen(YELLOW, 3))
        painter.drawLine(QPointF(slot_x, 53), QPointF(slot_x, 90))

    _set_font(painter, 14, 1)
    painter.setPen(QPen(YELLOW))
    _centered_text(painter, width / 2, 128, "INSERT COIN")
    painter.setPen(QPen(with_alpha(accent, 150), 2))
    for index in range(7):
        x = 24 + index * 24
        painter.drawLine(QPointF(x, 144), QPointF(x + 10, 144))
    painter.end()
    return pixmap


@cache
def offline_screen() -> QPixmap:
    """A dead screen: faint static and a notice."""
    width, height = 320, 240
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(2, 4, 6))
    painter = _painter(pixmap)
    rng = random.Random(0)
    painter.setPen(Qt.PenStyle.NoPen)
    for _ in range(500):
        painter.setBrush(with_alpha(WHITE, rng.randint(10, 50)))
        painter.drawRect(QRectF(rng.uniform(0, width), rng.uniform(0, height), 2, 2))
    _set_font(painter, 16, 2)
    painter.setPen(QPen(with_alpha(WHITE, 90)))
    _centered_text(painter, width / 2, height / 2 + 6, "NO SIGNAL")
    painter.end()
    return pixmap
