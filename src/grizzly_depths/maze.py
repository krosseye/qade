# SPDX-License-Identifier: GPL-3.0-or-later
"""The dungeon: a grid maze, its generation, and path finding. No Qt.

Generation is a recursive backtracker, which carves a perfect maze, then
braiding opens up a share of the dead ends, and loop injection knocks out a
fraction of the remaining interior walls.
"""

import random
from collections import deque
from collections.abc import Iterator
from functools import cached_property, lru_cache

Cell = tuple[int, int]
Segment = tuple[tuple[float, float], tuple[float, float]]

NORTH, EAST, SOUTH, WEST = range(4)
DIRECTIONS: tuple[Cell, ...] = ((0, 1), (1, 0), (0, -1), (-1, 0))


def opposite(direction: int) -> int:
    return (direction + 2) % 4


def _offset(point: Cell, direction: int) -> Cell:
    dx, dz = DIRECTIONS[direction]
    return (point[0] + dx, point[1] + dz)


class Maze:
    def __init__(
        self,
        width: int,
        height: int,
        rng: random.Random,
        loop_fraction: float,
        braid: float,
    ):
        """Generate a maze in which every cell is reachable from every other.

        Args:
            width, height: Size in cells.
            rng: Source of randomness, so a seed reproduces a maze.
            loop_fraction: Share of the perfect maze's leftover interior walls
                to remove, adding loops.
            braid: Share of the perfect maze's dead ends to open up.
        """
        self.width, self.height = width, height
        self._open: dict[Cell, set[int]] = {cell: set() for cell in self.cells()}
        self._carve_perfect(rng)
        self._braid(rng, braid)
        self._inject_loops(rng, loop_fraction)
        self.distances = lru_cache(maxsize=4)(self._distances)

    def _carve_perfect(self, rng: random.Random) -> None:
        """Carve a perfect maze: exactly one path between any two cells."""
        start = (rng.randrange(self.width), rng.randrange(self.height))
        visited = {start}
        stack = [start]
        while stack:
            cell = stack[-1]
            options = [
                (direction, neighbour)
                for direction, neighbour in self._around(cell)
                if neighbour not in visited
            ]
            if not options:
                stack.pop()  # dead end: back up to the last fork
                continue
            direction, neighbour = rng.choice(options)
            self._connect(cell, direction)
            visited.add(neighbour)
            stack.append(neighbour)

    def _braid(self, rng: random.Random, fraction: float) -> None:
        dead_ends = [cell for cell in self.cells() if len(self._open[cell]) == 1]
        rng.shuffle(dead_ends)
        for cell in dead_ends[: round(len(dead_ends) * fraction)]:
            if len(self._open[cell]) != 1:
                continue  # already opened, by joining a neighbouring dead end
            walls = [
                (direction, neighbour)
                for direction, neighbour in self._around(cell)
                if direction not in self._open[cell]
                and self._removable(cell, direction)
            ]
            if not walls:
                continue
            # Joining two dead ends removes both with one opening.
            joins = [wall for wall in walls if len(self._open[wall[1]]) == 1]
            direction, _ = rng.choice(joins or walls)
            self._connect(cell, direction)

    def _inject_loops(self, rng: random.Random, fraction: float) -> None:
        walls = [
            (cell, direction)
            for cell in self.cells()
            for direction, _ in self._around(cell)
            if direction in (NORTH, EAST) and direction not in self._open[cell]
        ]
        rng.shuffle(walls)
        for cell, direction in walls[: round(len(walls) * fraction)]:
            if self._removable(cell, direction):
                self._connect(cell, direction)

    def _removable(self, cell: Cell, direction: int) -> bool:
        """Whether knocking out this wall leaves every other wall attached.

        Walls meet at the grid's corner points. Removing one strands a wall
        at one of its corners if that wall is the only one left there and
        nothing else meets its far end either.
        """
        for corner in self._ends(cell, direction):
            others = [
                way
                for way in range(4)
                if self._wall_from(corner, way)
                and self._ends_at(corner, way) != self._ends(cell, direction)
            ]
            if len(others) == 1:
                far = _offset(corner, others[0])
                if sum(self._wall_from(far, way) for way in range(4)) == 1:
                    return False
        return True

    def _ends(self, cell: Cell, direction: int) -> frozenset[Cell]:
        """The two corner points of a cell's wall."""
        x, z = cell
        corners = {
            NORTH: ((x, z + 1), (x + 1, z + 1)),
            EAST: ((x + 1, z), (x + 1, z + 1)),
            SOUTH: ((x, z), (x + 1, z)),
            WEST: ((x, z), (x, z + 1)),
        }[direction]
        return frozenset(corners)

    def _ends_at(self, corner: Cell, way: int) -> frozenset[Cell]:
        return frozenset((corner, _offset(corner, way)))

    def _wall_from(self, corner: Cell, way: int) -> bool:
        """Whether a wall runs from a corner point one unit in ``way``."""
        x, z = corner
        # The two cells either side of that unit of wall.
        if way in (NORTH, SOUTH):
            row = z if way == NORTH else z - 1
            sides, crossing = ((x - 1, row), (x, row)), EAST
        else:
            column = x if way == EAST else x - 1
            sides, crossing = ((column, z - 1), (column, z)), NORTH
        inside = [self._inside(side) for side in sides]
        if all(inside):
            return crossing not in self._open[sides[0]]
        return any(inside)  # the outer wall

    def _inside(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self.width and 0 <= cell[1] < self.height

    def _connect(self, cell: Cell, direction: int) -> None:
        self._open[cell].add(direction)
        self._open[_offset(cell, direction)].add(opposite(direction))

    def cells(self) -> Iterator[Cell]:
        for z in range(self.height):
            for x in range(self.width):
                yield (x, z)

    def _around(self, cell: Cell) -> Iterator[tuple[int, Cell]]:
        """In-bounds neighbours, walls or not."""
        for direction, (dx, dz) in enumerate(DIRECTIONS):
            x, z = cell[0] + dx, cell[1] + dz
            if 0 <= x < self.width and 0 <= z < self.height:
                yield direction, (x, z)

    def is_open(self, cell: Cell, direction: int) -> bool:
        return direction in self._open[cell]

    def open_directions(self, cell: Cell) -> list[int]:
        return sorted(self._open[cell])

    def step(self, cell: Cell, direction: int) -> Cell:
        """The neighbouring cell in ``direction``. Doesn't check for a wall or
        the maze's edge; see ``is_open``."""
        return _offset(cell, direction)

    def _distances(self, start: Cell) -> dict[Cell, int]:
        """Path length from ``start`` to every cell; every cell is included.

        The result is cached and shared between callers: don't modify it.
        """
        distance = {start: 0}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            for direction in self._open[cell]:
                neighbour = self.step(cell, direction)
                if neighbour not in distance:
                    distance[neighbour] = distance[cell] + 1
                    queue.append(neighbour)
        return distance

    @cached_property
    def walls(self) -> list[Segment]:
        """Every wall as a floor-plan segment, each listed once."""
        segments: list[Segment] = []
        for x, z in self.cells():
            if not self.is_open((x, z), NORTH):
                segments.append(((x, z + 1), (x + 1, z + 1)))
            if not self.is_open((x, z), EAST):
                segments.append(((x + 1, z), (x + 1, z + 1)))
            if z == 0:
                segments.append(((x, 0), (x + 1, 0)))
            if x == 0:
                segments.append(((0, z), (0, z + 1)))
        return segments
