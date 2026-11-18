# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing things to recognise."""

import random
from itertools import pairwise
from math import cos, pi, sin

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from qade_engine.graphics import BLACK, Camera, Point3, with_alpha

from ..landmarks import Feature, Mark, Region
from ..maze import Cell, Segment

CRACK = QColor(186, 172, 236)
MORTAR = QColor(132, 108, 220)


def draw_mark(
    painter: QPainter, camera: Camera, wall: Segment, cell: Cell, mark: Mark, fog: float
) -> None:
    """Draw ``mark`` on the face of ``wall`` that looks into ``cell``.
    ``fog`` fades it with distance."""
    if fog <= 0:
        return
    rng = random.Random(mark.seed)
    face = _Face(painter, camera, wall, cell, fog)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    match mark.region:
        case Region.CRACKS:
            _crack(face, rng, length=0.24, width=1.1, alpha=140)
        case Region.BRICK:
            _bricks(face, rng, width=(0.28, 0.42), courses=3)
    match mark.feature:
        case Feature.HOLE:
            _hole(face, rng)
        case Feature.FISSURE:
            _fissure(face, rng)
        case Feature.BRICKWORK:
            _bricks(face, rng, width=(0.6, 0.75), courses=6, low=(0.12, 0.2))
        case Feature.BRICKED:
            _bricked(face, rng)
    painter.restore()


class _Face:
    """A wall face in its own coordinates: ``u`` along the wall (0 to 1),
    ``v`` up it (0 floor, 1 ceiling), ``w`` out from it into the cell."""

    def __init__(
        self, painter: QPainter, camera: Camera, wall: Segment, cell: Cell, fog: float
    ):
        self.painter, self.camera, self.fog = painter, camera, fog
        self.a, self.b = wall
        (ax, az), (bx, _) = wall
        # Out of the wall, towards the middle of the cell it faces.
        if ax == bx:
            self.n = (1 if cell[0] + 0.5 > ax else -1, 0)
        else:
            self.n = (0, 1 if cell[1] + 0.5 > az else -1)

    def at(self, u: float, v: float, w: float = 0.004) -> Point3:
        (ax, az), (bx, bz) = self.a, self.b
        nx, nz = self.n
        return (ax + (bx - ax) * u + nx * w, v, az + (bz - az) * u + nz * w)

    def u_of(self, point: Point3) -> float:
        """How far along the wall ``point`` is."""
        (ax, az), (bx, bz) = self.a, self.b
        x, _, z = point
        return (x - ax) / (bx - ax) if bx != ax else (z - az) / (bz - az)

    def pen(self, color: QColor, alpha: int, width: float) -> None:
        pen = QPen(with_alpha(color, int(alpha * self.fog)), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.painter.setPen(pen)

    def path(self, points: list[Point3]) -> None:
        for start, end in pairwise(points):
            line = self.camera.line(start, end)
            if line is not None:
                self.painter.drawLine(line)

    def fill(self, points: list[Point3], color: QColor, alpha: int) -> None:
        polygon = self.camera.polygon(points)
        if polygon is not None:
            self.painter.setBrush(with_alpha(color, int(alpha * self.fog)))
            self.painter.drawPolygon(polygon)
            self.painter.setBrush(Qt.BrushStyle.NoBrush)


def _crack(
    face: _Face, rng: random.Random, length: float, width: float, alpha: int
) -> None:
    """A zigzag down from the ceiling or up from the floor."""
    from_top = rng.random() < 0.5
    u = rng.uniform(0.2, 0.8)
    v = 0.98 if from_top else 0.02
    points = [face.at(u, v)]
    for _ in range(6):
        u += rng.uniform(-0.07, 0.07)
        v += (-1 if from_top else 1) * length / 6
        points.append(face.at(u, v))
    face.pen(CRACK, alpha, width)
    face.path(points)


def _bricks(
    face: _Face,
    rng: random.Random,
    width: tuple[float, float],
    courses: int,
    low: tuple[float, float] = (0.25, 0.45),
) -> None:
    """Plaster come away to show the brickwork: courses with staggered
    joints, ragged at the ends."""
    span = rng.uniform(*width)
    u0 = rng.uniform(0.08, max(0.08, 0.92 - span))
    u1 = u0 + span
    v0 = rng.uniform(*low)
    height = 0.09
    face.pen(MORTAR, 150, 1.1)
    for row in range(courses + 1):
        v = v0 + row * height
        a = u0 + rng.uniform(0, 0.06)
        b = u1 - rng.uniform(0, 0.06)
        face.path([face.at(a, v), face.at(b, v)])
        if row == courses:
            break
        u = a + (0.03 if row % 2 else 0.09)
        while u < b - 0.03:
            face.path([face.at(u, v), face.at(u, v + height)])
            u += 0.12


def _edge(
    face: _Face, rng: random.Random, cu: float, cv: float, size: float
) -> list[Point3]:
    """A broken outline on the wall."""
    corners = 9
    return [
        face.at(
            cu + cos(2 * pi * k / corners) * size * rng.uniform(0.6, 1.0),
            cv + sin(2 * pi * k / corners) * size * 1.2 * rng.uniform(0.6, 1.0),
        )
        for k in range(corners)
    ]


def _hole(face: _Face, rng: random.Random) -> None:
    """Part of the wall has fallen in."""
    cu, cv, size = rng.uniform(0.38, 0.62), rng.uniform(0.4, 0.58), 0.2
    edge = _edge(face, rng, cu, cv, size)
    face.painter.setPen(Qt.PenStyle.NoPen)
    face.fill(edge, BLACK, 255)
    face.pen(CRACK, 220, 1.6)
    face.path([*edge, edge[0]])
    for start in rng.sample(edge, 2):
        _run(face, rng, start, cu, cv)


def _run(face: _Face, rng: random.Random, start: Point3, cu: float, cv: float) -> None:
    """A short crack running outward from ``start``, away from (cu, cv)."""
    u, v = face.u_of(start), start[1]
    du, dv = u - cu, v - cv
    norm = (du * du + dv * dv) ** 0.5 or 1.0
    du, dv = du / norm, dv / norm
    points = [start]
    for _ in range(3):
        u += du * 0.06 + rng.uniform(-0.025, 0.025)
        v += dv * 0.06 + rng.uniform(-0.025, 0.025)
        points.append(face.at(u, v))
    face.pen(CRACK, 170, 1.1)
    face.path(points)


def _fissure(face: _Face, rng: random.Random) -> None:
    """A crack from floor to ceiling."""
    u = rng.uniform(0.3, 0.7)
    points = [face.at(u, 1.0)]
    for i in range(1, 9):
        u += rng.uniform(-0.06, 0.06)
        points.append(face.at(u, 1.0 - i / 8))
    face.pen(CRACK, 235, 1.7)
    face.path(points)
    fork = points[rng.randint(2, 5)]
    fork_u, fork_v = face.u_of(fork), fork[1]
    side = rng.choice((-1, 1))
    branch = [fork] + [
        face.at(fork_u + side * 0.07 * i, fork_v - 0.06 * i) for i in range(1, 4)
    ]
    face.pen(CRACK, 190, 1.1)
    face.path(branch)


def _bricked(face: _Face, rng: random.Random) -> None:
    """An old breach filled in."""
    cu, cv, size = rng.uniform(0.4, 0.6), rng.uniform(0.4, 0.55), 0.24
    edge = _edge(face, rng, cu, cv, size)
    outline = face.camera.polygon(edge)
    if outline is None:
        return
    painter = face.painter
    painter.save()
    clip = QPainterPath()
    clip.addPolygon(outline)
    painter.setClipPath(clip, Qt.ClipOperation.IntersectClip)
    height = 0.08
    top, bottom = cv + size * 1.25, cv - size * 1.25
    face.pen(MORTAR, 170, 1.1)
    v, row = bottom, 0
    while v < top:
        face.path([face.at(cu - size * 1.1, v), face.at(cu + size * 1.1, v)])
        u = cu - size * 1.1 + (0.04 if row % 2 else 0.09)
        while u < cu + size * 1.1:
            face.path([face.at(u, v), face.at(u, v + height)])
            u += 0.11
        v += height
        row += 1
    painter.restore()
    face.pen(CRACK, 210, 1.5)
    face.path([*edge, edge[0]])
