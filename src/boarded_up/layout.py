# SPDX-License-Identifier: GPL-3.0-or-later
"""The house is a grid of rooms joined by doors you buy, with boarded windows
on the outside walls."""

import random
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property

Tile = tuple[int, int]
Room = tuple[int, int]
Point = tuple[float, float]
Edge = tuple[float, float, float, float, frozenset[Room]]

ROOMS_X, ROOMS_Y = 4, 3
ROOM_W, ROOM_H = 11, 8
PITCH_X, PITCH_Y = ROOM_W + 1, ROOM_H + 1
DOOR_BASE, DOOR_STEP = 1000, 500
MAX_PLANKS = 5


class TileKind(IntEnum):
    WALL = 0
    FLOOR = 1
    DOOR = 2
    WINDOW = 3


def _center(tiles: list[Tile]) -> Point:
    return (
        sum(x for x, _ in tiles) / len(tiles) + 0.5,
        sum(y for _, y in tiles) / len(tiles) + 0.5,
    )


@dataclass(eq=False)
class Door:
    rooms: tuple[Room, Room]
    tiles: list[Tile]
    price: int
    open: bool = False

    @property
    def center(self) -> Point:
        return _center(self.tiles)


@dataclass(eq=False)
class Window:
    room: Room
    tiles: list[Tile]
    inside: Tile  # the floor tile a zombie lands on
    outward: tuple[int, int]  # unit step from inside to out
    planks: int = MAX_PLANKS

    @property
    def center(self) -> Point:
        return _center(self.tiles)


@dataclass(eq=False)
class House:
    width: int
    height: int
    kinds: list[list[TileKind]]
    room_of: dict[Tile, Room]
    start: Room
    doors: list[Door]
    windows: list[Window]
    depth: dict[Room, int]
    door_at: dict[Tile, Door] = field(default_factory=dict)
    pillars: dict[Room, list[Tile]] = field(default_factory=dict)
    open_rooms: set[Room] = field(init=False)  # kept current by ``open_door``

    def __post_init__(self) -> None:
        for door in self.doors:
            for tile in door.tiles:
                self.door_at[tile] = door
        self.open_rooms = self._reachable_rooms()

    def open_door(self, door: Door) -> None:
        """Opens a door, and with it the rooms beyond."""
        door.open = True
        self.open_rooms = self._reachable_rooms()

    def kind(self, tile: Tile) -> TileKind:
        x, y = tile
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.kinds[y][x]
        return TileKind.WALL

    def passable(self, tile: Tile) -> bool:
        kind = self.kind(tile)
        if kind is TileKind.FLOOR:
            return True
        return kind is TileKind.DOOR and self.door_at[tile].open

    def see_through(self, tile: Tile) -> bool:
        """Open floor, a window, or the yard outside the house."""
        x, y = tile
        if not (0 <= x < self.width and 0 <= y < self.height):
            return True
        return self.passable(tile) or self.kinds[y][x] is TileKind.WINDOW

    @cached_property
    def edges(self) -> list[Edge]:
        """Every side a wall tile shares with anything else, as ``(x0, y0, x1,
        y1)`` in tiles, with the rooms it faces: the house's outline."""
        out: list[Edge] = []
        for y in range(self.height):
            for x in range(self.width):
                if self.kinds[y][x] is not TileKind.WALL:
                    continue
                for dx, dy, side in (
                    (1, 0, (x + 1, y, x + 1, y + 1)),
                    (-1, 0, (x, y, x, y + 1)),
                    (0, 1, (x, y + 1, x + 1, y + 1)),
                    (0, -1, (x, y, x + 1, y)),
                ):
                    n = (x + dx, y + dy)
                    inside = 0 <= n[0] < self.width and 0 <= n[1] < self.height
                    kind = self.kind(n)
                    if kind is TileKind.WALL and inside:
                        continue
                    rooms: set[Room] = set()
                    if n in self.room_of:
                        rooms.add(self.room_of[n])
                    elif kind is TileKind.DOOR:
                        rooms.update(self.door_at[n].rooms)
                    elif kind is TileKind.WINDOW:
                        rooms.update(w.room for w in self.windows if n in w.tiles)
                    out.append((*side, frozenset(rooms)))
        return out

    def _reachable_rooms(self) -> set[Room]:
        """The start room and every room reached through open doors."""
        seen = {self.start}
        queue = deque([self.start])
        while queue:
            room = queue.popleft()
            for door in self.doors:
                if door.open and room in door.rooms:
                    other = door.rooms[1] if door.rooms[0] == room else door.rooms[0]
                    if other not in seen:
                        seen.add(other)
                        queue.append(other)
        return seen

    def distances(self, goal: Tile) -> dict[Tile, int]:
        """Steps from every passable tile to ``goal``, 4-connected."""
        dist = {goal: 0}
        queue = deque([goal])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in dist and self.passable((nx, ny)):
                    dist[(nx, ny)] = dist[(x, y)] + 1
                    queue.append((nx, ny))
        return dist


def room_origin(room: Room) -> Tile:
    """Top-left floor tile of a room."""
    return (room[0] * PITCH_X + 1, room[1] * PITCH_Y + 1)


def room_center(room: Room) -> Point:
    ox, oy = room_origin(room)
    return (ox + ROOM_W / 2, oy + ROOM_H / 2)


def build_house(rng: random.Random) -> House:
    width, height = ROOMS_X * PITCH_X + 1, ROOMS_Y * PITCH_Y + 1
    kinds = [[TileKind.WALL] * width for _ in range(height)]
    room_of: dict[Tile, Room] = {}
    rooms = [(rx, ry) for ry in range(ROOMS_Y) for rx in range(ROOMS_X)]
    for room in rooms:
        ox, oy = room_origin(room)
        for y in range(oy, oy + ROOM_H):
            for x in range(ox, ox + ROOM_W):
                kinds[y][x] = TileKind.FLOOR
                room_of[(x, y)] = room

    links = room_links(rng)
    start = (rng.choice(range(1, ROOMS_X - 1)), rng.choice((0, ROOMS_Y - 1)))
    depth = _room_depths(links, start)

    doors: list[Door] = []
    for room in rooms:
        ox, oy = room_origin(room)
        if frozenset((room, (room[0] + 1, room[1]))) in links:
            x = ox + ROOM_W
            ys = [oy + ROOM_H // 2 - 1, oy + ROOM_H // 2]
            doors.append(
                _door(room, (room[0] + 1, room[1]), [(x, y) for y in ys], depth)
            )
        if frozenset((room, (room[0], room[1] + 1))) in links:
            y = oy + ROOM_H
            xs = [ox + ROOM_W // 2, ox + ROOM_W // 2 + 1]
            doors.append(
                _door(room, (room[0], room[1] + 1), [(x, y) for x in xs], depth)
            )
    for door in doors:
        for x, y in door.tiles:
            kinds[y][x] = TileKind.DOOR

    windows: list[Window] = []
    for room in rooms:
        ox, oy = room_origin(room)
        sides = []
        if room[1] == 0:
            sides.append(("y", oy - 1, (0, -1)))
        if room[1] == ROOMS_Y - 1:
            sides.append(("y", oy + ROOM_H, (0, 1)))
        if room[0] == 0:
            sides.append(("x", ox - 1, (-1, 0)))
        if room[0] == ROOMS_X - 1:
            sides.append(("x", ox + ROOM_W, (1, 0)))
        for axis, line, outward in sides:
            if axis == "y":
                x = ox + rng.randrange(1, ROOM_W - 2)
                tiles = [(x, line), (x + 1, line)]
                inside = (x, line - outward[1])
            else:
                y = oy + rng.randrange(1, ROOM_H - 2)
                tiles = [(line, y), (line, y + 1)]
                inside = (line - outward[0], y)
            for tx, ty in tiles:
                kinds[ty][tx] = TileKind.WINDOW
            windows.append(Window(room, tiles, inside, outward))

    house = House(width, height, kinds, room_of, start, doors, windows, depth)
    for room in rooms:
        if room == start or rng.random() < 0.5:
            house.pillars[room] = _pillar(house, room, rng, big=room == start)
    return house


def _neighbours(room: Room) -> list[Room]:
    x, y = room
    near = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
    return [(nx, ny) for nx, ny in near if 0 <= nx < ROOMS_X and 0 <= ny < ROOMS_Y]


def room_links(rng: random.Random, loops: float = 0.15) -> set[frozenset[Room]]:
    """Which neighbouring rooms share a door.

    A random spanning tree joins every room, every dead end then gets a second
    door, and ``loops`` of the walls left get one too.
    """
    links: set[frozenset[Room]] = set()
    seen = {(0, 0)}
    trail = [(0, 0)]
    while trail:
        fresh = [n for n in _neighbours(trail[-1]) if n not in seen]
        if not fresh:
            trail.pop()
            continue
        room = rng.choice(fresh)
        links.add(frozenset((trail[-1], room)))
        seen.add(room)
        trail.append(room)
    rooms = sorted(seen)
    for room in rooms:
        shut = [n for n in _neighbours(room) if frozenset((room, n)) not in links]
        if len(_neighbours(room)) - len(shut) == 1:
            links.add(frozenset((room, rng.choice(shut))))
    for room in rooms:
        for n in _neighbours(room):
            if room < n and frozenset((room, n)) not in links and rng.random() < loops:
                links.add(frozenset((room, n)))
    return links


def _room_depths(links: set[frozenset[Room]], start: Room) -> dict[Room, int]:
    """Doors between ``start`` and every room."""
    depth = {start: 0}
    queue = deque([start])
    while queue:
        room = queue.popleft()
        for n in _neighbours(room):
            if n not in depth and frozenset((room, n)) in links:
                depth[n] = depth[room] + 1
                queue.append(n)
    return depth


def _door(a: Room, b: Room, tiles: list[Tile], depth: dict[Room, int]) -> Door:
    reach = max(depth[a], depth[b])
    return Door((a, b), tiles, DOOR_BASE + DOOR_STEP * (reach - 1))


def _pillar(house: House, room: Room, rng: random.Random, big: bool) -> list[Tile]:
    """A block of wall in the middle of a room: something to run rings round."""
    ox, oy = room_origin(room)
    w, h = (3, 2) if big else (rng.choice((2, 3)), rng.choice((1, 2)))
    x0 = ox + (ROOM_W - w) // 2 + (0 if big else rng.choice((-1, 0, 1)))
    y0 = oy + (ROOM_H - h) // 2
    tiles = [(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]
    for x, y in tiles:
        house.kinds[y][x] = TileKind.WALL
        house.room_of.pop((x, y), None)
    return tiles
