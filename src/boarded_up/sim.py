# SPDX-License-Identifier: GPL-3.0-or-later
"""The rules (rounds, the horde, and you). Positions are in tiles."""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from math import atan2, degrees, floor, hypot

from .layout import MAX_PLANKS, Door, House, Point, Tile, Window, room_center

PLAYER_SPEED = 6.0  # tiles/s
PLAYER_RADIUS = 0.3
FIRE_INTERVAL = 1 / 6
FIRE_RANGE = 9.0
HITS_TO_DOWN = 2
REGEN_TIME = 4.0
REACH = 1.7
PLANK_TIME = 0.6
BUY_TIME = 0.5
START_POINTS = 500

HIT_POINTS, KILL_POINTS, PLANK_POINTS = 5, 40, 10

ZOMBIE_RADIUS = 0.36
ATTACK_REACH = 0.8
WINDUP_TIME = 0.35
ATTACK_COOLDOWN = 1.0
CLIMB_TIME = 0.5
CLIMB_GAP = 1.0
CHASE_STRAIGHT = 4.0
LULL_TIME = 10.0
FIRST_LULL = 3.0


def toward(n: int, first: float, limit: float, half_life: float) -> float:
    return limit - (limit - first) * 0.5 ** ((n - 1) / half_life)


def zombie_speed(n: int) -> float:
    return toward(n, 1.7, 5.0, 12)


# Standing still fires as fast as you can, so it fails once health over
# spawn interval passes your fire rate (around round 6).
def zombie_health(n: int) -> int:
    return round(toward(n, 2, 18, 5))


def round_size(n: int) -> int:
    return round(toward(n, 10, 80, 8))


def max_alive(n: int) -> int:
    return round(toward(n, 6, 24, 8))


def spawn_interval(n: int) -> float:
    return toward(n, 2.5, 0.7, 6)


def tear_time(n: int) -> float:
    return toward(n, 1.6, 0.6, 10)


class ZombieState(Enum):
    BREACHING = auto()
    CLIMBING = auto()
    CHASING = auto()


@dataclass(eq=False)
class Zombie:
    x: float
    y: float
    hp: int
    window: Window | None
    state: ZombieState = ZombieState.BREACHING
    timer: float = 0.0
    windup: float = 0.0
    cooldown: float = 0.0
    flash: float = 0.0
    heading: float = 0.0
    prev: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        self.prev = (self.x, self.y)


@dataclass
class Effects:
    """What happened this step, for sounds and drawing. Cleared every step."""

    shots: list[tuple[Point, Point]] = field(default_factory=list)
    kills: list[Point] = field(default_factory=list)
    points: list[tuple[Point, int]] = field(default_factory=list)
    torn: list[Window] = field(default_factory=list)
    boarded: list[Window] = field(default_factory=list)
    opened: list[Door] = field(default_factory=list)
    hurt: bool = False
    round_started: int | None = None
    round_cleared: bool = False


@dataclass
class Job:
    """A window you're boarding up or a door you're buying, while you hold."""

    target: Window | Door
    progress: float = 0.0


def outside_spot(window: Window, place: int) -> Point:
    """Where the zombie ``place`` back in a window's queue stands."""
    cx, cy = window.center
    ox, oy = window.outward
    out = 0.9 + 0.8 * place
    return (cx + ox * out, cy + oy * out)


class Sim:
    def __init__(self, house: House, rng: random.Random):
        self.house = house
        self.rng = rng
        cx, cy = room_center(house.start)
        self.x, self.y = cx, cy + 2.5
        self.prev = (self.x, self.y)
        self.facing = -90.0
        self.hits = 0
        self.regen = 0.0
        self.points = START_POINTS
        self.earned = 0
        self.round = 0
        self.to_spawn = 0
        self.spawn_timer = 0.0
        self.lull = FIRST_LULL
        self.zombies: list[Zombie] = []
        self.fire_timer = 0.0
        self.job: Job | None = None
        self.planted = False
        self.downed = False
        self.effects = Effects()
        self._distances_from: Tile | None = None
        self._distances: dict[Tile, int] = {}

    @property
    def tile(self) -> Tile:
        return (int(self.x), int(self.y))

    @property
    def between_rounds(self) -> bool:
        return self.to_spawn == 0 and not self.zombies

    @property
    def work_share(self) -> float | None:
        """How far through the job in hand you are, 0 to 1, or None."""
        if self.job is None:
            return None
        duration = PLANK_TIME if isinstance(self.job.target, Window) else BUY_TIME
        return self.job.progress / duration

    def tearing(self) -> set[Window]:
        """Windows a zombie is tearing at right now."""
        return {
            z.window
            for z in self.zombies
            if z.state is ZombieState.BREACHING and z.window is not None and z.timer > 0
        }

    def distances_to_you(self) -> dict[Tile, int]:
        """Steps to you from every reachable tile."""
        if self._distances_from != self.tile:
            self._distances_from = self.tile
            self._distances = self.house.distances(self.tile)
        return self._distances

    def sees(self, x0: float, y0: float, x1: float, y1: float) -> bool:
        """A clear line through open tiles, windows and the yard outside."""
        steps = max(1, int(hypot(x1 - x0, y1 - y0) / 0.2))
        for i in range(1, steps):
            t = i / steps
            tile = (floor(x0 + (x1 - x0) * t), floor(y0 + (y1 - y0) * t))
            if not self.house.see_through(tile):
                return False
        return True

    def nearest_target(self) -> Zombie | None:
        best, best_d = None, FIRE_RANGE
        for z in self.zombies:
            d = hypot(z.x - self.x, z.y - self.y)
            if d < best_d and self.sees(self.x, self.y, z.x, z.y):
                best, best_d = z, d
        return best

    def workable(self) -> Window | Door | None:
        """The nearest damaged window or closed door within reach, if any."""
        open_rooms = self.house.open_rooms
        options: list[Window | Door] = [
            w
            for w in self.house.windows
            if w.room in open_rooms and w.planks < MAX_PLANKS
        ]
        options += [
            d
            for d in self.house.doors
            if not d.open and (d.rooms[0] in open_rooms or d.rooms[1] in open_rooms)
        ]
        best, best_d = None, REACH
        for option in options:
            d = hypot(option.center[0] - self.x, option.center[1] - self.y)
            if d <= best_d:
                best, best_d = option, d
        return best

    def step(self, dt: float, move: Point, act: bool) -> Effects:
        self.effects = Effects()
        self.prev = (self.x, self.y)
        for z in self.zombies:
            z.prev = (z.x, z.y)
        self._step_round(dt)
        fighting = not self.between_rounds
        self._step_player(dt, move, act)
        self._step_horde(dt)
        self.effects.round_cleared = fighting and self.between_rounds
        return self.effects

    def _step_round(self, dt: float) -> None:
        if self.between_rounds:
            self.lull -= dt
            if self.lull <= 0:
                self.round += 1
                self.to_spawn = round_size(self.round)
                self.spawn_timer = 1.0
                self.lull = LULL_TIME
                self.effects.round_started = self.round
            return
        self.spawn_timer -= dt
        if (
            self.to_spawn
            and self.spawn_timer <= 0
            and len(self.zombies) < max_alive(self.round)
        ):
            self.spawn_timer = spawn_interval(self.round)
            self._spawn()
            self.to_spawn -= 1

    def _spawn(self) -> None:
        """At a window of an open room, favouring ones near you."""
        to_you = self.distances_to_you()
        windows = [w for w in self.house.windows if w.room in self.house.open_rooms]
        weights = [1.0 / (1.0 + to_you.get(w.inside, 99) / 6.0) for w in windows]
        window = self.rng.choices(windows, weights)[0]
        queue = sum(
            1
            for z in self.zombies
            if z.window is window and z.state is ZombieState.BREACHING
        )
        x, y = outside_spot(window, queue)
        self.zombies.append(Zombie(x, y, zombie_health(self.round), window))

    def _step_player(self, dt: float, move: Point, act: bool) -> None:
        if self.hits:
            self.regen -= dt
            if self.regen <= 0:
                self.hits = 0
        self.fire_timer -= dt
        self.planted = act
        if not act:
            self.job = None
            mx, my = move
            length = hypot(mx, my)
            if length > 0:
                mx, my = mx / length, my / length
                self.facing = degrees(atan2(my, mx)) % 360
                self.x, self.y = self._slide(
                    self.x,
                    self.y,
                    mx * PLAYER_SPEED * dt,
                    my * PLAYER_SPEED * dt,
                    PLAYER_RADIUS,
                )
            return

        target = self.workable()
        if isinstance(target, Door) and self.points < target.price:
            target = None
        if target is None:
            self.job = None
            zombie = self.nearest_target()
            if zombie is not None:
                self.facing = degrees(atan2(zombie.y - self.y, zombie.x - self.x))
                if self.fire_timer <= 0:
                    self.fire_timer = FIRE_INTERVAL
                    self._shoot(zombie)
            return
        if self.job is None or self.job.target is not target:
            self.job = Job(target)
        job = self.job
        job.progress += dt
        if isinstance(target, Window):
            if job.progress >= PLANK_TIME:
                job.progress = 0.0
                target.planks += 1
                self._earn(PLANK_POINTS)
                self.effects.boarded.append(target)
                self.effects.points.append((target.center, PLANK_POINTS))
        elif job.progress >= BUY_TIME:
            job.progress = 0.0
            self.points -= target.price
            self.house.open_door(target)
            self._distances_from = None
            self.effects.opened.append(target)

    def _earn(self, amount: int) -> None:
        self.points += amount
        self.earned += amount

    def _shoot(self, z: Zombie) -> None:
        self.effects.shots.append(((self.x, self.y), (z.x, z.y)))
        z.hp -= 1
        z.flash = 0.08
        self._earn(HIT_POINTS)
        if z.hp <= 0:
            self.zombies.remove(z)
            self._earn(KILL_POINTS)
            self.effects.kills.append((z.x, z.y))
            self.effects.points.append(((z.x, z.y), HIT_POINTS + KILL_POINTS))

    def _step_horde(self, dt: float) -> None:
        to_you = self.distances_to_you()
        speed = zombie_speed(self.round)
        for z in self.zombies:
            z.flash = max(0.0, z.flash - dt)
            z.cooldown = max(0.0, z.cooldown - dt)
            if z.state is ZombieState.BREACHING:
                self._breach(z, dt)
            elif z.state is ZombieState.CLIMBING:
                self._climb(z, dt)
            else:
                self._chase(z, dt, speed, to_you)
        self._separate()

    def _breach(self, z: Zombie, dt: float) -> None:
        w = z.window
        assert w is not None
        ahead = [
            o
            for o in self.zombies
            if o.window is w and o.state is not ZombieState.CHASING
        ]
        place = ahead.index(z)
        tx, ty = outside_spot(w, place)
        z.x += (tx - z.x) * min(1.0, 4 * dt)
        z.y += (ty - z.y) * min(1.0, 4 * dt)
        z.heading = degrees(atan2(-w.outward[1], -w.outward[0]))
        if place != 0 or any(o.state is ZombieState.CLIMBING for o in ahead):
            return
        z.timer += dt
        if w.planks == 0:
            if z.timer >= CLIMB_GAP:
                z.state, z.timer = ZombieState.CLIMBING, CLIMB_TIME
            return
        if z.timer >= tear_time(self.round):
            z.timer = 0.0
            w.planks -= 1
            self.effects.torn.append(w)

    def _climb(self, z: Zombie, dt: float) -> None:
        w = z.window
        assert w is not None
        if w.planks and z.timer > CLIMB_TIME / 2:
            z.state, z.timer = ZombieState.BREACHING, 0.0
            return
        z.timer -= dt
        sx, sy = outside_spot(w, 0)
        ix, iy = w.inside[0] + 0.5, w.inside[1] + 0.5
        t = 1.0 - max(0.0, z.timer) / CLIMB_TIME
        z.x, z.y = sx + (ix - sx) * t, sy + (iy - sy) * t
        if z.timer <= 0:
            z.state, z.window = ZombieState.CHASING, None

    def _chase(
        self, z: Zombie, dt: float, speed: float, to_you: dict[Tile, int]
    ) -> None:
        d = hypot(self.x - z.x, self.y - z.y)
        if z.windup > 0:
            z.windup -= dt
            if z.windup <= 0:
                z.cooldown = ATTACK_COOLDOWN
                if d <= ATTACK_REACH + 0.15 and not self.downed:
                    self._hurt()
            return
        if d <= ATTACK_REACH and z.cooldown <= 0:
            z.windup = WINDUP_TIME
            return
        gx, gy = self.x, self.y
        if d >= CHASE_STRAIGHT or not self.sees(z.x, z.y, self.x, self.y):
            tx, ty = int(z.x), int(z.y)
            options = [
                (to_you[n], n)
                for n in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1))
                if n in to_you
            ]
            if options:
                _, (nx, ny) = min(options)
                gx, gy = nx + 0.5, ny + 0.5
        dx, dy = gx - z.x, gy - z.y
        length = hypot(dx, dy)
        if length > 1e-6:
            step = min(length, speed * dt)
            z.heading = degrees(atan2(dy, dx))
            z.x, z.y = self._slide(
                z.x, z.y, dx / length * step, dy / length * step, ZOMBIE_RADIUS
            )

    def _hurt(self) -> None:
        self.hits += 1
        self.regen = REGEN_TIME
        self.effects.hurt = True
        if self.hits >= HITS_TO_DOWN:
            self.downed = True

    def _separate(self) -> None:
        chasing = [z for z in self.zombies if z.state is ZombieState.CHASING]
        gap = 2 * ZOMBIE_RADIUS
        for i, a in enumerate(chasing):
            for b in chasing[i + 1 :]:
                dx, dy = b.x - a.x, b.y - a.y
                d = hypot(dx, dy)
                if 1e-6 < d < gap:
                    push = (gap - d) / 2 / d
                    a.x, a.y = self._slide(
                        a.x, a.y, -dx * push, -dy * push, ZOMBIE_RADIUS
                    )
                    b.x, b.y = self._slide(
                        b.x, b.y, dx * push, dy * push, ZOMBIE_RADIUS
                    )

    def _slide(
        self, x: float, y: float, dx: float, dy: float, r: float
    ) -> tuple[float, float]:
        x, y = x + dx, y + dy
        for _ in range(2):
            for ty in range(int(y) - 1, int(y) + 2):
                for tx in range(int(x) - 1, int(x) + 2):
                    if self.house.passable((tx, ty)):
                        continue
                    cx = min(max(x, tx), tx + 1)
                    cy = min(max(y, ty), ty + 1)
                    ox, oy = x - cx, y - cy
                    d = hypot(ox, oy)
                    if d < r:
                        if d < 1e-9:
                            ox, oy, d = -dx or 1e-3, -dy, hypot(-dx or 1e-3, -dy)
                        x += ox / d * (r - d)
                        y += oy / d * (r - d)
        return x, y
