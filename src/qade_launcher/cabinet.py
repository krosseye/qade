# SPDX-License-Identifier: GPL-3.0-or-later
"""A wireframe arcade cabinet: a side profile extruded across its width."""

from collections.abc import Callable
from math import cos, radians, sin

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QTransform,
)

from qade_engine.graphics import WHITE, Camera, Point3, blend, hairline, with_alpha

from .art import BODY, stipple

PROFILE = [
    (0.05, 0.0),
    (0.05, 1.05),
    (-0.30, 1.10),
    (-0.30, 1.27),
    (0.06, 1.46),
    (0.22, 2.40),
    (0.0, 2.53),
    (0.0, 3.0),
    (0.95, 3.0),
    (0.95, 0.0),
]
DOOR, SKIRT, PANEL_FRONT, PANEL, SCREEN, SLOPE, MARQUEE, TOP, BACK, BOTTOM = range(10)
LEFT_SIDE, RIGHT_SIDE = -1, -2
HALF_WIDTH = 0.6
PIVOT_DEPTH = 0.45
SCREEN_CENTER: Point3 = (0.0, 1.93, 0.14)

SHADE = 120
OFFLINE_SHADE = 165

Art = Callable[[], QPixmap]


class Cabinet:
    """One cabinet standing in the aisle, drawn in perspective."""

    def __init__(
        self,
        x: float,
        z: float,
        yaw: float,
        accent: QColor,
        art: dict[int, Art],
        offline: bool = False,
    ):
        """Place a cabinet in the aisle.

        Args:
            x, z: Floor position of the cabinet's middle.
            yaw: Degrees the cabinet is turned; 0 faces the camera's start.
            accent: Trim and highlight color.
            art: Textures by face (DOOR, PANEL, SCREEN, MARQUEE).
            offline: Drawn darker, as a cabinet that can't be played.
        """
        self.x, self.z, self.yaw = x, z, yaw
        self.accent = accent
        self.art = art
        self.offline = offline
        self._cos, self._sin = cos(radians(yaw)), sin(radians(yaw))

    def world(self, x: float, y: float, z: float) -> Point3:
        """A local point (x across, y up, z depth from the front) in world space."""
        depth = z - PIVOT_DEPTH
        return (
            self.x + x * self._cos + depth * self._sin,
            y,
            self.z - x * self._sin + depth * self._cos,
        )

    def _direction(self, x: float, y: float, z: float) -> Point3:
        return (x * self._cos + z * self._sin, y, -x * self._sin + z * self._cos)

    def footprint(self, grow: float = 0.0) -> list[Point3]:
        front, back = -0.32 - grow, 0.95 + grow
        half = HALF_WIDTH + grow
        return [
            self.world(-half, 0, front),
            self.world(half, 0, front),
            self.world(half, 0, back),
            self.world(-half, 0, back),
        ]

    def draw_floor_glow(
        self, painter: QPainter, camera: Camera, brightness: float
    ) -> None:
        """The pool of light under a selected cabinet."""
        if brightness <= 0.01:
            return
        polygon = camera.polygon(self.footprint(grow=0.6))
        if polygon is None:
            return
        bounds = polygon.boundingRect()
        gradient = QRadialGradient(bounds.center(), max(bounds.width(), 1.0) * 0.6)
        gradient.setColorAt(0.0, with_alpha(self.accent, int(90 * brightness)))
        gradient.setColorAt(1.0, with_alpha(self.accent, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPolygon(polygon)

    def draw(self, painter: QPainter, camera: Camera, brightness: float) -> None:
        """Draw the cabinet's visible faces, from unselected (``brightness``
        0: shaded, plain trim) to selected (1: lit, accent glow on its edges)."""
        eye = (camera.pose.x, camera.pose.y, camera.pose.z)
        faces: list[tuple[float, int, list[Point3]]] = []  # (distance, kind, points)

        for side in (-1, 1):
            points = [self.world(side * HALF_WIDTH, y, z) for z, y in PROFILE]
            kind = LEFT_SIDE if side < 0 else RIGHT_SIDE
            faces.append(self._face(eye, kind, points, self._direction(side, 0, 0)))
        for index in range(len(PROFILE)):
            if index == BOTTOM:
                continue
            z0, y0 = PROFILE[index]
            z1, y1 = PROFILE[(index + 1) % len(PROFILE)]
            points = [
                self.world(-HALF_WIDTH, y0, z0),
                self.world(HALF_WIDTH, y0, z0),
                self.world(HALF_WIDTH, y1, z1),
                self.world(-HALF_WIDTH, y1, z1),
            ]
            faces.append(
                self._face(eye, index, points, self._direction(0, z1 - z0, -(y1 - y0)))
            )

        visible = [face for face in faces if face[0] >= 0]
        visible.sort(key=lambda face: -face[0])
        shade = (OFFLINE_SHADE if self.offline else SHADE) * (1.0 - brightness)
        for _, kind, points in visible:
            self._draw_face(painter, camera, kind, points, brightness, int(shade))

    @staticmethod
    def _face(
        eye: Point3, kind: int, points: list[Point3], normal: Point3
    ) -> tuple[float, int, list[Point3]]:
        """(distance from the eye, or -1 if it faces away, kind, points)."""
        count = len(points)
        center = [sum(point[axis] for point in points) / count for axis in range(3)]
        to_eye = [eye[axis] - center[axis] for axis in range(3)]
        if sum(normal[axis] * to_eye[axis] for axis in range(3)) <= 0:
            return (-1.0, kind, points)
        return (sum(value * value for value in to_eye) ** 0.5, kind, points)

    def _draw_face(
        self,
        painter: QPainter,
        camera: Camera,
        kind: int,
        points: list[Point3],
        brightness: float,
        shade: int,
    ) -> None:
        polygon = camera.polygon(points)
        if polygon is None:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        quad: list[QPointF] = []
        if kind in self.art:
            corners = (points[3], points[2], points[1], points[0])
            projected = [camera.project(corner) for corner in corners]
            quad = [corner for corner in projected if corner is not None]
        if len(quad) == 4:
            _warp(painter, self.art[kind](), quad)
            if shade > 0:
                painter.setBrush(QColor(0, 0, 0, shade))
                painter.drawPolygon(polygon)
        else:
            light = 1.0 - shade / 255
            painter.setBrush(BODY)
            painter.drawPolygon(polygon)
            dots = 60 if kind == LEFT_SIDE else 80 if kind == RIGHT_SIDE else 50
            painter.setBrush(stipple(with_alpha(WHITE, int(dots * light))))
            painter.drawPolygon(polygon)
            if kind in (LEFT_SIDE, RIGHT_SIDE):
                self._draw_stripe(painter, camera, kind, light)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._outline(painter, polygon, brightness)

    def _draw_stripe(
        self, painter: QPainter, camera: Camera, kind: int, light: float
    ) -> None:
        """The accent band along a side panel."""
        side = -1 if kind == LEFT_SIDE else 1
        stripe = [
            self.world(side * HALF_WIDTH, y, z)
            for z, y in ((0.05, 0.36), (0.95, 0.36), (0.95, 0.46), (0.05, 0.46))
        ]
        polygon = camera.polygon(stripe)
        if polygon is not None:
            painter.setBrush(with_alpha(self.accent, int(150 * light)))
            painter.drawPolygon(polygon)

    def _outline(
        self, painter: QPainter, polygon: QPolygonF, brightness: float
    ) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        resting = with_alpha(WHITE, 90 if self.offline else 160)
        if brightness > 0.05:
            painter.setPen(QPen(with_alpha(self.accent, int(45 * brightness)), 6))
            painter.drawPolygon(polygon)
            painter.setPen(QPen(blend(resting, self.accent, brightness), 1.4))
        else:
            painter.setPen(hairline(resting))
        painter.drawPolygon(polygon)


def _warp(painter: QPainter, pixmap: QPixmap, quad: list[QPointF]) -> None:
    """Draw ``pixmap`` stretched onto a projected quad (perspective-correct)."""
    source = QPolygonF(
        [
            QPointF(0, 0),
            QPointF(pixmap.width(), 0),
            QPointF(pixmap.width(), pixmap.height()),
            QPointF(0, pixmap.height()),
        ]
    )
    transform = QTransform()
    if not QTransform.quadToQuad(source, QPolygonF(quad), transform):
        return
    painter.save()
    painter.setTransform(transform, True)
    painter.drawPixmap(0, 0, pixmap)
    painter.restore()
