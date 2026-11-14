# SPDX-License-Identifier: GPL-3.0-or-later
"""The corridor the cabinets stand in: wire frames, floor lanes, ceiling lights,
and a glowing far wall tinted to the selected game."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen

from qade_engine.core import clamp, lerp
from qade_engine.graphics import WHITE, Camera, Point3, blend, hairline, with_alpha

from .art import WIRE

HALF_WIDTH = 2.9
HEIGHT = 4.0
FRAME_SPACING = 1.6  # distance between the wire frames
LANES = 9  # floor lines running down the aisle
FADE_DISTANCE = 22.0  # lines are invisible this far ahead


def _fade(camera: Camera, z: float) -> float:
    """1 near the camera, 0 at ``FADE_DISTANCE``."""
    ahead = z - camera.pose.z
    return clamp(1.0 - ahead / FADE_DISTANCE, 0.0, 1.0)


def draw_aisle(
    painter: QPainter, camera: Camera, start_z: float, end_z: float, glow: QColor
) -> None:
    """Draw the corridor from ``start_z`` to its far wall at ``end_z``."""
    painter.save()
    _draw_far_wall(painter, camera, end_z, glow)

    for index in range(LANES):
        x = -HALF_WIDTH + 2 * HALF_WIDTH * index / (LANES - 1)
        centrality = 1.0 - abs(x) / HALF_WIDTH
        color = blend(WIRE, glow, 0.35 + 0.65 * centrality)
        _faded_line(painter, camera, (x, 0, start_z), (x, 0, end_z), color)
    for x in (-HALF_WIDTH, HALF_WIDTH):
        _faded_line(painter, camera, (x, HEIGHT, start_z), (x, HEIGHT, end_z), WIRE)

    z = end_z - FRAME_SPACING
    while z > start_z:
        alpha = _fade(camera, z)
        if alpha > 0 and camera.depth((0, 0, z)) > 0:
            corners = [
                (-HALF_WIDTH, 0, z),
                (HALF_WIDTH, 0, z),
                (HALF_WIDTH, HEIGHT, z),
                (-HALF_WIDTH, HEIGHT, z),
            ]
            pen = hairline(with_alpha(WIRE, int(150 * alpha)))
            for index in range(4):
                line = camera.line(corners[index], corners[(index + 1) % 4])
                if line is not None:
                    painter.setPen(pen)
                    painter.drawLine(line)
            light = camera.line((-0.45, HEIGHT - 0.02, z), (0.45, HEIGHT - 0.02, z))
            if light is not None:
                painter.setPen(QPen(with_alpha(WHITE, int(200 * alpha)), 2.5))
                painter.drawLine(light)
        z -= FRAME_SPACING
    painter.restore()


def _faded_line(
    painter: QPainter, camera: Camera, start: Point3, end: Point3, color: QColor
) -> None:
    """A lengthwise line, split into segments so it fades with distance."""
    segments = 8

    def point(t: float) -> Point3:
        return (
            lerp(start[0], end[0], t),
            lerp(start[1], end[1], t),
            lerp(start[2], end[2], t),
        )

    for index in range(segments):
        a, b = point(index / segments), point((index + 1) / segments)
        alpha = _fade(camera, (a[2] + b[2]) / 2)
        if alpha <= 0:
            continue
        line = camera.line(a, b)
        if line is not None:
            painter.setPen(hairline(with_alpha(color, int(170 * alpha))))
            painter.drawLine(line)


def _draw_far_wall(painter: QPainter, camera: Camera, z: float, glow: QColor) -> None:
    polygon = camera.polygon(
        [
            (-HALF_WIDTH, 0, z),
            (HALF_WIDTH, 0, z),
            (HALF_WIDTH, HEIGHT, z),
            (-HALF_WIDTH, HEIGHT, z),
        ]
    )
    if polygon is None:
        return
    bounds = polygon.boundingRect()
    gradient = QLinearGradient(bounds.topLeft(), bounds.bottomLeft())
    gradient.setColorAt(0.0, with_alpha(glow, 30))
    gradient.setColorAt(0.75, with_alpha(glow, 110))
    gradient.setColorAt(1.0, with_alpha(glow, 60))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawPolygon(polygon)
