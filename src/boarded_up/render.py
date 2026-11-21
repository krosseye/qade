# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass
from math import atan2, cos, hypot, pi, radians, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from qade_engine.graphics import (
    WHITE,
    YELLOW,
    Opacity,
    blend,
    current_theme,
    draw_centered,
    hairline,
    make_font,
    with_alpha,
)

from .layout import (
    MAX_PLANKS,
    ROOM_H,
    ROOM_W,
    ROOMS_X,
    ROOMS_Y,
    Door,
    House,
    Room,
    Tile,
    TileKind,
    Window,
    room_origin,
)
from .sim import PLANK_POINTS, PLAYER_RADIUS, ZOMBIE_RADIUS, Sim, Zombie, ZombieState

TILE = 24.0  # px per tile
TRACER_LIFE = 0.08  # s

WALL = QColor(128, 158, 206)
WALL_FILL = QColor(16, 22, 36)
FLOOR = QColor(70, 92, 128)
SHUT = QColor(64, 72, 92)
WOOD = QColor(220, 164, 96)
WOOD_DARK = QColor(92, 58, 28)
ROT = QColor(128, 222, 84)
ROT_FILL = QColor(18, 38, 12)
ROT_EYES = QColor(236, 255, 150)
ICHOR = QColor(96, 160, 40)
LANTERN = QColor(255, 226, 160)
LANTERN_REACH = 4.5  # tiles


@dataclass(slots=True)
class Tracer:
    start: QPointF
    end: QPointF
    life: float = TRACER_LIFE


@dataclass(slots=True)
class Popup:
    at: QPointF
    text: str
    life: float = 1.0


def to_px(x: float, y: float) -> QPointF:
    """A position in tiles in world pixels."""
    return QPointF(x * TILE, y * TILE)


def _tiles_rect(tiles: list[Tile]) -> QRectF:
    """The rectangle covering some tiles in world pixels."""
    xs = [x for x, _ in tiles]
    ys = [y for _, y in tiles]
    x0, y0 = min(xs), min(ys)
    return QRectF(
        x0 * TILE, y0 * TILE, (max(xs) + 1 - x0) * TILE, (max(ys) + 1 - y0) * TILE
    )


def _room_rect(room: Room) -> QRectF:
    ox, oy = room_origin(room)
    return QRectF(ox * TILE, oy * TILE, ROOM_W * TILE, ROOM_H * TILE)


class HouseArt:
    """The house's floors and walls."""

    def __init__(self, house: House):
        self.house = house
        self._walls = QPainterPath()
        for y in range(house.height):
            for x in range(house.width):
                if house.kinds[y][x] is TileKind.WALL:
                    self._walls.addRect(QRectF(x * TILE, y * TILE, TILE, TILE))
        self._walls = self._walls.simplified()
        self._rebuild()

    def _rebuild(self) -> None:
        open_rooms = frozenset(self.house.open_rooms)
        self._open = open_rooms
        self._floors = QPainterPath()
        self._boards = QPainterPath()
        self._shut = QPainterPath()
        for room in ((x, y) for y in range(ROOMS_Y) for x in range(ROOMS_X)):
            rect = _room_rect(room)
            if room in open_rooms:
                self._floors.addRect(rect)
                _add_boards(self._boards, rect)
            else:
                self._shut.addRect(rect)
        for door in self.house.doors:
            if door.open:
                self._floors.addRect(_tiles_rect(door.tiles))
        self._lit = QPainterPath()
        self._dim = QPainterPath()
        for x0, y0, x1, y1, faces in self.house.edges:
            path = self._lit if faces & open_rooms else self._dim
            path.moveTo(to_px(x0, y0))
            path.lineTo(to_px(x1, y1))

    def draw(self, painter: QPainter, lantern: QPointF | None = None) -> None:
        if self.house.open_rooms != self._open:
            self._rebuild()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillPath(
            self._shut, QBrush(with_alpha(SHUT, 60), Qt.BrushStyle.BDiagPattern)
        )
        painter.fillPath(self._floors, with_alpha(WALL_FILL, Opacity.STRONG))
        painter.strokePath(self._boards, hairline(with_alpha(FLOOR, 70)))

        if lantern is not None:
            reach = LANTERN_REACH * TILE
            glow = QRadialGradient(lantern, reach)
            glow.setColorAt(0.0, with_alpha(LANTERN, 46))
            glow.setColorAt(0.6, with_alpha(LANTERN, 14))
            glow.setColorAt(1.0, with_alpha(LANTERN, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(lantern, reach, reach)

        painter.fillPath(self._walls, WALL_FILL)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        lit = QPen(WALL, 2)
        lit.setCapStyle(Qt.PenCapStyle.SquareCap)
        dim = QPen(with_alpha(SHUT, 150), 1.5)
        dim.setCapStyle(Qt.PenCapStyle.SquareCap)
        painter.strokePath(self._dim, dim)
        painter.strokePath(self._lit, lit)
        painter.restore()


def _add_boards(path: QPainterPath, rect: QRectF) -> None:
    rows = round(rect.height() / TILE)
    for row in range(rows + 1):
        y = rect.top() + row * TILE
        path.moveTo(rect.left(), y)
        path.lineTo(rect.right(), y)
        if row == rows:
            break
        x = rect.left() + (row % 3) * TILE
        while x < rect.right():
            if x > rect.left():
                path.moveTo(x, y)
                path.lineTo(x, y + TILE)
            x += 3 * TILE


def draw_doors(painter: QPainter, house: House, points: int, now: float) -> None:
    theme = current_theme()
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    make_font(painter, 9, spacing=1)
    for door in house.doors:
        rect = _tiles_rect(door.tiles)
        vertical = rect.height() > rect.width()
        if door.open:
            painter.setPen(QPen(with_alpha(WOOD, Opacity.MEDIUM), 2))
            if vertical:
                hinge = QPointF(rect.center().x(), rect.top())
                painter.drawLine(hinge, hinge + QPointF(rect.height() * 0.7, 0))
            else:
                hinge = QPointF(rect.left(), rect.center().y())
                painter.drawLine(hinge, hinge + QPointF(0, rect.width() * 0.7))
            continue
        reachable = bool(set(door.rooms) & house.open_rooms)
        affordable = reachable and points >= door.price
        slab = rect.adjusted(6, 1, -6, -1) if vertical else rect.adjusted(1, 6, -1, -6)
        painter.setBrush(WOOD_DARK if reachable else with_alpha(WOOD_DARK, 70))
        edge = WOOD if reachable else with_alpha(SHUT, 150)
        if affordable:
            edge = blend(WOOD, theme.highlight, 0.5 + 0.5 * sin(now * 5))
        painter.setPen(QPen(edge, 2 if affordable else 1.5))
        painter.drawRect(slab)
        painter.setPen(QPen(with_alpha(edge, 120), 1))
        if vertical:
            painter.drawLine(
                QPointF(slab.center().x(), slab.top()),
                QPointF(slab.center().x(), slab.bottom()),
            )
        else:
            painter.drawLine(
                QPointF(slab.left(), slab.center().y()),
                QPointF(slab.right(), slab.center().y()),
            )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if reachable:
            here = door.rooms[0] if door.rooms[0] in house.open_rooms else door.rooms[1]
            hx, hy = _room_side(house, door, here)
            label = f"{door.price}"
            width = painter.fontMetrics().horizontalAdvance(label)
            painter.setPen(QPen(theme.highlight if affordable else theme.text_muted))
            painter.drawText(
                QPointF(
                    rect.center().x() + hx * 26 - width / 2,
                    rect.center().y() + hy * 22 + 4,
                ),
                label,
            )
    painter.restore()


def _room_side(house: House, door: Door, room: Room) -> tuple[int, int]:
    """Which way from the door ``room`` lies."""
    x, y = door.tiles[0]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if house.room_of.get((x + dx, y + dy)) == room:
            return dx, dy
    return 0, 0


def draw_windows(
    painter: QPainter, house: House, tearing: set[Window], now: float
) -> None:
    theme = current_theme()
    backing = QPen(WOOD_DARK, 4.2)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for w in house.windows:
        lit = w.room in house.open_rooms
        rect = _tiles_rect(w.tiles)
        along_x = rect.width() > rect.height()
        painter.fillRect(rect, with_alpha(WALL, 30 if lit else 10))
        wood = WOOD if lit else with_alpha(SHUT, 150)
        if lit and w in tearing and int(now * 10) % 2:
            wood = theme.danger
        painter.setPen(QPen(WALL if lit else with_alpha(SHUT, 150), 2))
        if along_x:
            for x in (rect.left(), rect.right()):
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        else:
            for y in (rect.top(), rect.bottom()):
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        mid = rect.center()
        if w.planks == 0:
            painter.setPen(
                QPen(theme.danger if lit else wood, 1.5, Qt.PenStyle.DashLine)
            )
            if along_x:
                painter.drawLine(
                    QPointF(rect.left(), mid.y()), QPointF(rect.right(), mid.y())
                )
            else:
                painter.drawLine(
                    QPointF(mid.x(), rect.top()), QPointF(mid.x(), rect.bottom())
                )
            continue
        front = QPen(wood, 2.2)
        for i in range(w.planks):
            t = (i + 0.5) / MAX_PLANKS
            tilt = 3.0 if i % 2 else -3.0
            if along_x:
                y = rect.top() + rect.height() * t
                a = QPointF(rect.left() - 3, y - tilt)
                b = QPointF(rect.right() + 3, y + tilt)
            else:
                x = rect.left() + rect.width() * t
                a = QPointF(x - tilt, rect.top() - 3)
                b = QPointF(x + tilt, rect.bottom() + 3)
            painter.setPen(backing)
            painter.drawLine(a, b)
            painter.setPen(front)
            painter.drawLine(a, b)
    painter.restore()


def draw_zombie(painter: QPainter, at: QPointF, z: Zombie) -> None:
    theme = current_theme()
    r = ZOMBIE_RADIUS * TILE
    x, y = at.x(), at.y()
    winding = z.windup > 0
    edge = WHITE if z.flash > 0 else ROT
    if z.state is ZombieState.BREACHING:
        edge = with_alpha(edge, 190)
    a = radians(z.heading)
    fx, fy = cos(a), sin(a)
    sx, sy = -fy, fx
    reach = r * (1.9 if winding else 1.3)
    spread = r * (0.95 if winding else 0.6)
    # A shamble: the arms aren't quite level.
    sway = 0.18 * r * sin(z.x * 3.1 + z.y * 2.3)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(theme.danger if winding else edge, 2.4 if winding else 1.8))
    for side in (-1, 1):
        shoulder = QPointF(x + sx * side * r * 0.8, y + sy * side * r * 0.8)
        lag = sway * side
        hand = QPointF(
            x + fx * (reach + lag) + sx * side * spread,
            y + fy * (reach + lag) + sy * side * spread,
        )
        painter.drawLine(shoulder, hand)
    painter.setPen(QPen(edge, 1.8))
    painter.setBrush(ROT_FILL)
    painter.drawEllipse(at, r, r)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(WHITE if z.flash else ROT_EYES)
    for side in (-1, 1):
        ex = x + fx * r * 0.45 + sx * side * r * 0.35
        ey = y + fy * r * 0.45 + sy * side * r * 0.35
        painter.drawEllipse(QPointF(ex, ey), 1.7, 1.7)
    painter.restore()


def draw_player(painter: QPainter, at: QPointF, sim: Sim, now: float) -> None:
    theme = current_theme()
    r = PLAYER_RADIUS * TILE
    x, y = at.x(), at.y()
    a = radians(sim.facing)
    fx, fy = cos(a), sin(a)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = theme.danger if sim.hits and int(now * 8) % 2 else LANTERN
    painter.setPen(QPen(color, 2))
    painter.setBrush(with_alpha(color, Opacity.MEDIUM))
    tip = QPointF(x + fx * r * 1.6, y + fy * r * 1.6)
    left = QPointF(x - fx * r + fy * r * 1.1, y - fy * r - fx * r * 1.1)
    right = QPointF(x - fx * r - fy * r * 1.1, y - fy * r + fx * r * 1.1)
    back = QPointF(x - fx * r * 0.3, y - fy * r * 0.3)
    painter.drawPolygon([tip, left, back, right])
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if sim.planted:
        painter.setPen(QPen(with_alpha(LANTERN, Opacity.STRONG), 1.5))
        box = r * 2.4
        for k in range(4):
            c = pi / 4 + k * pi / 2
            cx, cy = x + cos(c) * box, y + sin(c) * box
            painter.drawLine(QPointF(cx, cy), QPointF(cx - cos(c) * 5, cy))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - sin(c) * 5))
    work = sim.work_share
    if work is not None:
        ring = QRectF(x - r * 3, y - r * 3, r * 6, r * 6)
        painter.setPen(QPen(with_alpha(theme.highlight, 60), 3))
        painter.drawEllipse(ring)
        painter.setPen(QPen(theme.highlight, 3))
        painter.drawArc(ring, 90 * 16, -int(360 * 16 * min(1.0, work)))
    painter.restore()


def draw_tracers(painter: QPainter, tracers: list[Tracer]) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for t in tracers:
        fade = max(0.0, t.life / TRACER_LIFE)
        painter.setPen(QPen(with_alpha(YELLOW, int(230 * fade)), 1.6))
        painter.drawLine(t.start, t.end)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(WHITE, int(200 * fade)))
        dx, dy = t.end.x() - t.start.x(), t.end.y() - t.start.y()
        d = hypot(dx, dy) or 1.0
        painter.drawEllipse(
            t.start + QPointF(dx / d * 10, dy / d * 10), 3.5 * fade, 3.5 * fade
        )
    painter.restore()


def draw_popups(painter: QPainter, popups: list[Popup]) -> None:
    theme = current_theme()
    painter.save()
    make_font(painter, 10, spacing=1)
    for p in popups:
        rise = (1.0 - p.life) * 24
        painter.setPen(
            QPen(with_alpha(theme.highlight, int(255 * min(1.0, p.life * 2))))
        )
        painter.drawText(p.at + QPointF(-10, -14 - rise), p.text)
    painter.restore()


def draw_offscreen(painter: QPainter, view: QRectF, targets: list[QPointF]) -> None:
    theme = current_theme()
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    cx, cy = view.center().x(), view.center().y()
    inner = view.adjusted(14, 14, -14, -14)
    for target in targets:
        if view.contains(target):
            continue
        dx, dy = target.x() - cx, target.y() - cy
        scale = min(
            (inner.width() / 2) / abs(dx) if dx else 1e9,
            (inner.height() / 2) / abs(dy) if dy else 1e9,
        )
        ex, ey = cx + dx * scale, cy + dy * scale
        far = hypot(target.x() - ex, target.y() - ey)
        alpha = int(255 * max(0.25, 1.0 - far / 500))
        a = atan2(dy, dx)
        tip = QPointF(ex + cos(a) * 7, ey + sin(a) * 7)
        left = QPointF(ex + cos(a + 2.5) * 6, ey + sin(a + 2.5) * 6)
        right = QPointF(ex + cos(a - 2.5) * 6, ey + sin(a - 2.5) * 6)
        painter.setPen(QPen(with_alpha(theme.danger, alpha), 1.5))
        painter.setBrush(with_alpha(theme.danger, alpha // 2))
        painter.drawPolygon([tip, left, right])
    painter.restore()


def draw_hurt(painter: QPainter, width: float, height: float, amount: float) -> None:
    if amount <= 0:
        return
    theme = current_theme()
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    edge = 60
    for i in range(6):
        alpha = int(70 * amount * (1 - i / 6))
        painter.setPen(QPen(with_alpha(theme.danger, alpha), edge / 6))
        inset = edge / 12 + i * edge / 6
        painter.drawRect(QRectF(inset, inset, width - 2 * inset, height - 2 * inset))
    painter.restore()


def draw_prompt(
    painter: QPainter, width: float, height: float, sim: Sim, now: float
) -> None:
    theme = current_theme()
    target = sim.workable()
    if target is None:
        return
    if isinstance(target, Window):
        text, color = f"[HOLD] BOARD UP   +{PLANK_POINTS}", theme.highlight
    elif sim.points >= target.price:
        text, color = f"[HOLD] OPEN DOOR   {target.price}", theme.highlight
    else:
        text, color = (
            f"DOOR {target.price}   NEED {target.price - sim.points} MORE",
            theme.text_muted,
        )
    if not sim.planted and int(now * 2) % 2:
        color = with_alpha(color, 140)
    make_font(painter, 13, spacing=3)
    painter.setPen(QPen(color))
    draw_centered(painter, text, width, height - 30)


def draw_banner(
    painter: QPainter, width: float, height: float, sim: Sim, since: float
) -> None:
    theme = current_theme()
    if sim.round == 0:
        return
    if since < 2.5:
        alpha = int(255 * min(1.0, (2.5 - since) / 0.6))
        make_font(painter, 30, spacing=10)
        painter.setPen(QPen(with_alpha(theme.danger, alpha)))
        draw_centered(painter, f"ROUND {sim.round}", width, height * 0.36)
    elif sim.between_rounds:
        make_font(painter, 14, spacing=5)
        painter.setPen(QPen(theme.success))
        draw_centered(painter, f"ROUND {sim.round} SURVIVED", width, height * 0.36)
        make_font(painter, 10, spacing=3)
        painter.setPen(QPen(theme.text_muted))
        draw_centered(
            painter,
            f"NEXT IN {max(0.0, sim.lull):.0f}   BOARD UP AND SPEND",
            width,
            height * 0.36 + 22,
        )
