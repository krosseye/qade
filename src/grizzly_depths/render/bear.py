# SPDX-License-Identifier: GPL-3.0-or-later
"""The bear: a silhouette that faces you, glares, and rears."""

from math import pi, sin

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
)

from qade_engine.graphics import (
    NEAR,
    ORANGE,
    RED,
    Camera,
    with_alpha,
)

from ..bear import Bear, Mood
from ..config import REAR_TIME
from .fog import fog_at

BEAR_EDGE = ORANGE
BEAR_FILL = QColor(24, 12, 6)


def _polygon(points: list[tuple[float, float]]) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in points])


def _mirrored(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(-x, y) for x, y in points]


_BODY = [
    (0.0, 0.08),
    (-0.20, 0.12),
    (-0.27, 0.30),
    (-0.29, 0.50),
    (-0.25, 0.62),
    (-0.13, 0.69),
    (0.13, 0.69),
    (0.25, 0.62),
    (0.29, 0.50),
    (0.27, 0.30),
    (0.20, 0.12),
]
_LEG = [(-0.23, 0.0), (-0.05, 0.0), (-0.07, 0.20), (-0.23, 0.22)]
_ARM = [
    (-0.21, 0.64),
    (-0.35, 0.79),
    (-0.43, 0.87),
    (-0.48, 0.81),
    (-0.41, 0.72),
    (-0.27, 0.51),
]
_HEAD = [
    (-0.13, 0.65),
    (-0.155, 0.77),
    (-0.10, 0.86),
    (0.0, 0.885),
    (0.10, 0.86),
    (0.155, 0.77),
    (0.13, 0.65),
    (0.06, 0.59),
    (-0.06, 0.59),
]
_MOUTH = [(-0.075, 0.705), (0.075, 0.705), (0.05, 0.615), (-0.05, 0.615)]
_FANGS = [
    [(-0.055, 0.705), (-0.04, 0.655), (-0.025, 0.705)],
    [(-0.04, 0.615), (-0.028, 0.65), (-0.016, 0.615)],
]
_EYE = [(-0.095, 0.795), (-0.03, 0.775), (-0.04, 0.758), (-0.088, 0.772)]
_SHUT_EYE = ((-0.095, 0.785), (-0.062, 0.758), (-0.03, 0.77))
_BROW = ((-0.12, 0.83), (-0.02, 0.79))
_CLAWS = [
    ((-0.43 - 0.018 * k, 0.865 - 0.028 * k), (-0.47 - 0.03 * k, 0.93 - 0.03 * k))
    for k in range(3)
]


def _bear_silhouette() -> QPainterPath:
    """The bear's outline: body, head, limbs and ears as one path."""
    parts = [_BODY, _HEAD, _LEG, _mirrored(_LEG), _ARM, _mirrored(_ARM)]
    path = QPainterPath()
    for part in parts:
        piece = QPainterPath()
        piece.addPolygon(_polygon(part))
        piece.closeSubpath()
        path = path.united(piece)
    for x in (-0.11, 0.11):
        ear = QPainterPath()
        ear.addEllipse(QPointF(x, 0.865), 0.045, 0.04)
        path = path.united(ear)
    return path.simplified()


BEAR_SHAPE = _bear_silhouette()
BEAR_MOUTH = _polygon(_MOUTH)
BEAR_FANGS = [_polygon(f) for fang in _FANGS for f in (fang, _mirrored(fang))]
BEAR_EYES = [_polygon(_EYE), _polygon(_mirrored(_EYE))]


def _shut_eye(points: tuple[tuple[float, float], ...]) -> QPainterPath:
    (x0, y0), (cx, cy), (x1, y1) = points
    path = QPainterPath(QPointF(x0, y0))
    path.quadTo(QPointF(cx, cy), QPointF(x1, y1))
    return path


BEAR_SHUT_EYES = [_shut_eye(_SHUT_EYE), _shut_eye(tuple(_mirrored(list(_SHUT_EYE))))]
BEAR_DETAIL_LINES = [_BROW, *_CLAWS]
BEAR_DETAIL_LINES += [((-a[0], a[1]), (-b[0], b[1])) for a, b in BEAR_DETAIL_LINES]
BONE = QColor(235, 225, 200)


def draw_bear(
    painter: QPainter, camera: Camera, x: float, z: float, bear: Bear, distance: float
) -> None:
    """Draw ``bear`` standing at floor-plan ``(x, z)``, as a billboard that
    always faces the camera. ``distance`` from the eye sets how far it fades
    into the dark. Draws nothing when it is behind or right up against the
    camera."""
    depth = camera.depth((x, 0.0, z))
    if depth < NEAR * 2:
        return
    feet = camera.project((x, 0.0, z))
    if feet is None:
        return
    bob = 0.03 * abs(sin(bear.progress * pi)) if bear.awake else 0.0
    scale = camera.focal / depth
    transform = QTransform().translate(feet.x(), feet.y()).scale(scale, -scale)
    transform.translate(0, bob)
    if bear.mood is Mood.REARING:
        rise = sin(pi * (1.0 - bear.timer / REAR_TIME))
        transform.scale(1.0 - 0.05 * rise, 1.0 + 0.22 * rise)

    fog = max(fog_at(distance), 0.25)
    painter.save()
    painter.setTransform(transform, True)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(BEAR_FILL)
    painter.drawPath(BEAR_SHAPE)
    fur = QBrush(with_alpha(BEAR_EDGE, int(70 * fog)), Qt.BrushStyle.Dense6Pattern)
    fur.setTransform(transform.inverted()[0])
    painter.setBrush(fur)
    painter.drawPath(BEAR_SHAPE)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(_cosmetic(with_alpha(BEAR_EDGE, int(255 * fog)), 2.0))
    painter.drawPath(BEAR_SHAPE)

    painter.setBrush(QColor(70, 6, 10))
    painter.drawPolygon(BEAR_MOUTH)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(with_alpha(BONE, int(255 * max(fog, 0.5))))
    for fang in BEAR_FANGS:
        painter.drawPolygon(fang)

    painter.setPen(_cosmetic(with_alpha(BONE, int(230 * fog)), 1.6))
    for start, end in BEAR_DETAIL_LINES:
        painter.drawLine(QPointF(*start), QPointF(*end))

    if not bear.awake:
        painter.setPen(_cosmetic(with_alpha(BEAR_EDGE, int(255 * fog)), 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for lid in BEAR_SHUT_EYES:
            painter.drawPath(lid)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(RED, int(255 * max(fog, 0.7))))
        for eye in BEAR_EYES:
            painter.drawPolygon(eye)
    painter.restore()


def _cosmetic(color: QColor, width: float) -> QPen:
    """A pen whose width is in pixels, whatever the bear's scale."""
    pen = QPen(color, width)
    pen.setCosmetic(True)
    return pen
