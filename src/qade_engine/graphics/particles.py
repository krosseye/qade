# SPDX-License-Identifier: GPL-3.0-or-later
"""Particle effects: short-lived visuals that never affect gameplay.

A game describes each effect as a ``Burst``: a tuple of ``ParticleEffect``
layers, so one event can combine, say, a shockwave and debris. It keeps its
bursts in its own module and calls ``ParticleSystem.emit`` when things happen.

An effect normally lives on the canvas. It can instead be emitted around an
``anchor``: a point the game places afresh every frame, with a scale, such as
something seen in perspective. Its particles then move relative to that point
and are drawn wherever it is.
"""

import math
import random
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from enum import Enum, auto

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from .palette import blend, with_alpha

MAX_PARTICLES = 1500
_COLOR_STEPS = 32
_ALPHA_STEPS = 32


class Shape(Enum):
    """How a particle is drawn.

    Attributes:
        DOT: A filled circle. ``size`` is its diameter.
        STREAK: A line trailing behind the motion.
        SHARD: A tumbling line segment. ``size`` is its length.
        RING: An expanding circle outline. ``size`` is its final radius.
    """

    DOT = auto()
    STREAK = auto()
    SHARD = auto()
    RING = auto()


@dataclass(frozen=True, eq=False)
class ParticleEffect:
    """One layer of an effect. Ranges are (low, high), picked from per particle.

    Attributes:
        count: Particles emitted.
        life: Seconds each particle lives.
        colors: Start and end of the colour gradient.
        shapes: Shapes, one picked at random per particle.
        speed: Speed in px/s.
        size: Size in px; see ``Shape``.
        spread: Degrees, centred on the emit heading.
        min_count: Floor on ``count`` when ``emit`` scales it down.
        drag: Fraction of speed lost per second.
        spin: Shard spin in degrees/s, in a random direction.
        width: Pen width in px for lines and outlines.
        streak: Seconds of travel a streak covers.
        fade_time: Opaque until this much life remains. None fades over the
            whole life.
        color_time: Seconds the gradient takes. None spans each particle's life.
        brush: Fill for dots.
        outline: Also outline dots with the pen.
    """

    count: int
    life: tuple[float, float]
    colors: tuple[QColor, QColor]
    shapes: tuple[Shape, ...] = (Shape.DOT,)
    speed: tuple[float, float] = (0.0, 0.0)
    size: tuple[float, float] = (2.0, 2.0)
    spread: float = 360.0
    min_count: int = 1
    drag: float = 0.0
    spin: tuple[float, float] = (0.0, 0.0)
    width: float = 2.0
    streak: float = 0.1
    fade_time: float | None = None
    color_time: float | None = None
    brush: Qt.BrushStyle = Qt.BrushStyle.SolidPattern
    outline: bool = False
    _styles: dict = field(default_factory=dict, init=False, repr=False)

    def style(self, progress: float, opacity: float) -> tuple[QPen, QBrush]:
        """The cached pen and brush for a point along the gradient and an opacity.

        Args:
            progress: How far along the colour gradient, from 0 to 1.
            opacity: From 0 to 1.

        Returns:
            The pen and brush to draw with.
        """
        key = (
            min(int(max(progress, 0.0) * _COLOR_STEPS), _COLOR_STEPS - 1),
            round(min(opacity, 1.0) * (_ALPHA_STEPS - 1)),
        )
        style = self._styles.get(key)
        if style is None:
            color = with_alpha(
                blend(*self.colors, key[0] / (_COLOR_STEPS - 1)),
                round(key[1] * 255 / (_ALPHA_STEPS - 1)),
            )
            if self.outline or any(s is not Shape.DOT for s in self.shapes):
                pen = QPen(color, self.width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            else:
                pen = QPen(Qt.PenStyle.NoPen)
            brush = QBrush(color, self.brush) if Shape.DOT in self.shapes else QBrush()
            style = self._styles[key] = (pen, brush)
        return style


Burst = tuple[ParticleEffect, ...]

Placement = Callable[[Hashable], tuple[float, float, float] | None]


class Particle:
    """One live particle. ``ParticleSystem`` fills every field when it emits.

    Attributes:
        effect: The layer it came from.
        anchor: The anchor it moves with, or None if ``x`` and ``y`` are on
            the canvas.
        shape: How it is drawn.
        x: Position.
        y: Position.
        vx: Velocity in px/s.
        vy: Velocity in px/s.
        life: Seconds remaining.
        max_life: Seconds it lives in all.
        size: Size in px.
        angle: Shard angle in radians.
        spin: Shard spin in radians/s.
    """

    __slots__ = (
        "anchor",
        "angle",
        "effect",
        "life",
        "max_life",
        "shape",
        "size",
        "spin",
        "vx",
        "vy",
        "x",
        "y",
    )
    effect: ParticleEffect
    anchor: Hashable | None
    shape: Shape
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    angle: float
    spin: float


class ParticleSystem:
    """Every live particle, stepped with the simulation and recycled through a free list.

    Attributes:
        budget: Most particles alive at once.
        items: The live particles.
    """

    def __init__(self, budget: int = MAX_PARTICLES) -> None:
        """Creates an empty system.

        Args:
            budget: Most particles alive at once. Emits beyond it are dropped.
        """
        self.budget = budget
        self.items: list[Particle] = []
        self._free: list[Particle] = []
        self._rng = random.Random()

    def clear(self) -> None:
        """Removes every particle."""
        self._free.extend(self.items)
        self.items = []

    def emit(
        self,
        burst: Burst,
        x: float,
        y: float,
        heading: float = 0.0,
        scale: float = 1.0,
        anchor: Hashable | None = None,
    ) -> None:
        """Spawns every layer of a burst.

        Args:
            burst: The layers to spawn.
            x: Canvas x, or the offset from ``anchor`` (usually 0).
            y: Canvas y, or the offset from ``anchor`` (usually 0).
            heading: Direction in degrees, 0 up and clockwise, that the spread
                centres on.
            scale: Multiplier on each layer's count, floored at ``min_count``.
                Must be finite: NaN or infinity raises. ``PlayField.area_scale``
                is always finite for a field with a non-zero size.
            anchor: Any object naming a point the game places when drawing.
                Pass the same one for the whole burst.
        """
        for effect in burst:
            count = max(effect.min_count, int(effect.count * scale))
            count = min(count, self.budget - len(self.items))
            for _ in range(count):
                self.items.append(self._spawn(effect, x, y, heading, anchor))

    def _spawn(self, effect, x, y, heading, anchor) -> Particle:
        half_spread = effect.spread / 2
        direction = math.radians(heading + self._rng.uniform(-half_spread, half_spread))
        speed = self._rng.uniform(*effect.speed)

        p = self._free.pop() if self._free else Particle()
        p.effect = effect
        p.anchor = anchor
        p.shape = self._rng.choice(effect.shapes)
        p.x, p.y = x, y
        p.vx, p.vy = math.sin(direction) * speed, -math.cos(direction) * speed
        p.life = p.max_life = self._rng.uniform(*effect.life)
        p.size = self._rng.uniform(*effect.size)
        p.angle = self._rng.uniform(0, math.tau)
        p.spin = math.radians(self._rng.uniform(*effect.spin)) * self._rng.choice(
            (-1, 1)
        )
        return p

    def update(self, dt: float) -> None:
        """Moves the particles and recycles the expired ones.

        Args:
            dt: Step length in seconds.
        """
        alive: list[Particle] = []
        for p in self.items:
            if p.effect.drag:
                damping = max(0.0, 1.0 - p.effect.drag * dt)
                p.vx *= damping
                p.vy *= damping
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.angle += p.spin * dt
            p.life -= dt
            (alive if p.life > 0 else self._free).append(p)
        self.items = alive

    def draw(
        self, painter: QPainter, ahead: float = 0.0, place: Placement | None = None
    ) -> None:
        """Draws every particle.

        Args:
            painter: The painter to draw with.
            ahead: Seconds past the last step to move the particles on.
            place: Where each anchor is this frame, as ``(x, y, scale)`` in
                view units, or None to hide it, such as behind the camera. The
                scale applies to the whole burst, pen widths included.
                Anchored particles are hidden when this is None.
        """
        current = None
        held: Hashable | None = None
        visible = True
        for p in self.items:
            if p.anchor is not held:
                if held is not None:
                    painter.restore()
                held, visible, current = p.anchor, True, None
                if held is not None:
                    spot = place(held) if place is not None else None
                    visible = spot is not None
                    painter.save()
                    if spot is not None:
                        painter.translate(spot[0], spot[1])
                        painter.scale(spot[2], spot[2])
            if not visible or p.life <= 0:
                continue

            effect = p.effect
            style = effect.style(
                1.0 - p.life / (effect.color_time or p.max_life),
                p.life / (effect.fade_time or p.max_life),
            )
            if style is not current:
                painter.setPen(style[0])
                painter.setBrush(style[1])
                current = style

            x, y = p.x + p.vx * ahead, p.y + p.vy * ahead
            match p.shape:
                case Shape.DOT:
                    painter.drawEllipse(
                        QRectF(x - p.size / 2, y - p.size / 2, p.size, p.size)
                    )
                case Shape.STREAK:
                    tail_x = x - p.vx * effect.streak
                    tail_y = y - p.vy * effect.streak
                    painter.drawLine(QLineF(tail_x, tail_y, x, y))
                case Shape.SHARD:
                    half_x = math.cos(p.angle) * p.size / 2
                    half_y = math.sin(p.angle) * p.size / 2
                    painter.drawLine(
                        QLineF(x - half_x, y - half_y, x + half_x, y + half_y)
                    )
                case Shape.RING:
                    progress = 1.0 - p.life / p.max_life
                    radius = p.size * (1.0 - (1.0 - progress) ** 2)
                    painter.drawEllipse(QPointF(x, y), radius, radius)
        if held is not None:
            painter.restore()
