# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing the dungeon in the vector style: dark walls with bright edges."""

from collections.abc import Callable
from functools import partial
from math import cos, pi, sin

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
)

from qade_engine.graphics import (
    BLACK,
    NEAR,
    YELLOW,
    Camera,
    Point3,
    blend,
    hairline,
    with_alpha,
)

from ..config import VIEW_RADIUS
from ..level import Level
from .bear import draw_bear
from .fog import fog_at

WALL = QColor(150, 120, 255)
WALL_FILL = QColor(26, 18, 56)
FLOOR = QColor(90, 70, 170)


WALL_HEIGHT = 1.0
BEACON_HIDE = 0.45  # hide the 3D beacon closer than this: draw_attunement takes over


class _Culler:
    """Rejects geometry wholly outside the view's left or right edge."""

    def __init__(self, camera: Camera, view_width: float):
        self.camera = camera
        self.slope = (view_width / 2) / camera.focal + 0.05

    def visible(self, points: list[Point3]) -> bool:
        view = [self.camera.to_view(point) for point in points]
        if all(z < NEAR for _, _, z in view):
            return False
        if all(x > self.slope * z for x, _, z in view):
            return False
        return not all(-x > self.slope * z for x, _, z in view)


def draw_dungeon(
    painter: QPainter,
    camera: Camera,
    view_width: float,
    level: Level,
    bear_position: tuple[float, float],
    beacon_angle: float,
) -> None:
    """Draw the floor, walls, exit beacon and bear within ``VIEW_RADIUS`` of
    the camera. ``beacon_angle`` is the beacon's spin, in radians. Leaves the
    painter's state as it found it."""
    culler = _Culler(camera, view_width)
    eye_x, eye_z = camera.pose.x, camera.pose.z

    def distance(x: float, z: float) -> float:
        return ((x - eye_x) ** 2 + (z - eye_z) ** 2) ** 0.5

    painter.save()
    _draw_floor(painter, camera, culler, level, distance)

    items: list[tuple[float, Callable[[], None]]] = []
    for (x0, z0), (x1, z1) in level.maze.walls:
        d = distance((x0 + x1) / 2, (z0 + z1) / 2)
        if d > VIEW_RADIUS:
            continue
        quad = [
            (x0, 0.0, z0),
            (x1, 0.0, z1),
            (x1, WALL_HEIGHT, z1),
            (x0, WALL_HEIGHT, z0),
        ]
        if culler.visible(quad):
            items.append((d, partial(_draw_wall, painter, camera, quad, d)))

    exit_x, exit_z = level.exit[0] + 0.5, level.exit[1] + 0.5
    d = distance(exit_x, exit_z)
    if BEACON_HIDE < d < VIEW_RADIUS:
        items.append(
            (d, partial(_draw_beacon, painter, camera, exit_x, exit_z, beacon_angle, d))
        )

    bear_x, bear_z = bear_position
    d = distance(bear_x, bear_z)
    if d < VIEW_RADIUS:
        items.append(
            (d, partial(draw_bear, painter, camera, bear_x, bear_z, level.bear, d))
        )

    items.sort(key=lambda item: -item[0])
    for _, draw in items:
        draw()
    painter.restore()


def _draw_floor(
    painter: QPainter,
    camera: Camera,
    culler: _Culler,
    level: Level,
    distance: Callable[[float, float], float],
) -> None:
    """Faint grid lines on the floor and ceiling, and a glow on the exit cell."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    reach = int(VIEW_RADIUS) + 1
    cx, cz = int(camera.pose.x), int(camera.pose.z)
    maze = level.maze
    xs = range(max(0, cx - reach), min(maze.width, cx + reach) + 1)
    zs = range(max(0, cz - reach), min(maze.height, cz + reach) + 1)
    for x in xs:
        for z in zs:
            for dx, dz in ((0, 1), (1, 0)):
                if x + dx not in xs or z + dz not in zs:
                    continue
                fog = fog_at(distance(x + dx / 2, z + dz / 2))
                if fog <= 0:
                    continue
                for y, alpha in ((0.0, 90), (WALL_HEIGHT, 55)):
                    segment: list[Point3] = [(x, y, z), (x + dx, y, z + dz)]
                    if culler.visible(segment):
                        _line(
                            painter,
                            camera,
                            segment,
                            with_alpha(FLOOR, int(alpha * fog)),
                        )

    ex, ez = level.exit
    tile: list[Point3] = [
        (ex, 0.0, ez),
        (ex + 1, 0.0, ez),
        (ex + 1, 0.0, ez + 1),
        (ex, 0.0, ez + 1),
    ]
    polygon = camera.polygon(tile)
    fog = fog_at(distance(ex + 0.5, ez + 0.5))
    if polygon is not None and fog > 0:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(YELLOW, int(70 * fog)))
        painter.drawPolygon(polygon)


def _line(painter: QPainter, camera: Camera, segment, color: QColor) -> None:
    line = camera.line(*segment)
    if line is not None:
        painter.setPen(hairline(color))
        painter.drawLine(line)


def _draw_wall(painter: QPainter, camera: Camera, quad, distance: float) -> None:
    polygon = camera.polygon(quad)
    if polygon is None:
        return
    fog = fog_at(distance)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(blend(BLACK, WALL_FILL, fog))
    painter.drawPolygon(polygon)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    color = with_alpha(WALL, int(255 * fog))
    painter.setPen(QPen(color, 1.6) if fog > 0.7 else hairline(color))
    painter.drawPolygon(polygon)


def _draw_beacon(
    painter: QPainter, camera: Camera, x: float, z: float, angle: float, distance: float
) -> None:
    """A spinning wire diamond hovering over the exit."""
    radius, middle = 0.16, 0.5
    ring = [
        (
            x + radius * cos(angle + k * pi / 2),
            middle,
            z + radius * sin(angle + k * pi / 2),
        )
        for k in range(4)
    ]
    top, bottom = (x, middle + radius * 1.4, z), (x, middle - radius * 1.4, z)
    edges = [(top, p) for p in ring] + [(bottom, p) for p in ring]
    edges += [(ring[k], ring[(k + 1) % 4]) for k in range(4)]
    fog = fog_at(distance)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(with_alpha(YELLOW, int(255 * fog)), 1.6))
    for start, end in edges:
        line = camera.line(start, end)
        if line is not None:
            painter.drawLine(line)
