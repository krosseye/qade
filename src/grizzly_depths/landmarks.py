# SPDX-License-Identifier: GPL-3.0-or-later
"""Things to recognise."""

import random
from dataclasses import dataclass
from enum import Enum, auto

from .maze import Cell, Maze, Segment


class Region(Enum):
    CRACKS = auto()
    BRICK = auto()
    BARE = auto()


class Feature(Enum):
    HOLE = auto()
    FISSURE = auto()
    BRICKWORK = auto()
    BRICKED = auto()


@dataclass(frozen=True)
class Mark:
    """What's on one face of a wall: the region's touch, a feature, or
    both. ``seed`` varies the shape so no two look quite alike."""

    region: Region | None
    feature: Feature | None
    seed: int


Marks = dict[tuple[Segment, Cell], Mark]  # keyed by (wall, the cell it faces)

REGION_SHARE = 0.45
FEATURE_SHARE = 0.4
# path steps:
NEAR_LAIR = 2  # claw marks own these walls
FEATURE_SPACING = 3


def build_marks(maze: Maze, seed: int, to_lair: dict[Cell, int]) -> Marks:
    """Marks for every wall face, drawn from their own ``seed`` so the same
    place always looks the same."""
    rng = random.Random(seed)
    regions = _regions(maze, rng)
    walls = _walls_by_cell(maze)

    featured: dict[tuple[Segment, Cell], Feature] = {}
    taken: list[Cell] = []
    decisions = list(maze.cells())
    rng.shuffle(decisions)
    for cell in decisions:
        ways = maze.open_directions(cell)
        straight = len(ways) == 2 and ways[1] - ways[0] == 2
        if straight or not walls[cell] or to_lair[cell] <= NEAR_LAIR:
            continue
        if rng.random() >= FEATURE_SHARE:
            continue
        near = maze.distances(cell)
        if any(near[other] < FEATURE_SPACING for other in taken):
            continue
        taken.append(cell)
        featured[(rng.choice(walls[cell]), cell)] = rng.choice(list(Feature))

    marks: Marks = {}
    for cell in maze.cells():
        if to_lair[cell] <= NEAR_LAIR:
            continue
        for wall in walls[cell]:
            region = regions[cell]
            touch = (
                region
                if region is not Region.BARE and rng.random() < REGION_SHARE
                else None
            )
            feature = featured.get((wall, cell))
            if touch or feature:
                marks[(wall, cell)] = Mark(touch, feature, rng.randrange(1 << 30))
    return marks


def _regions(maze: Maze, rng: random.Random) -> dict[Cell, Region]:
    """Each cell takes the region of its nearest seed point,
    so patch borders wander."""
    count = max(3, (maze.width * maze.height) // 18)
    seeds = [
        (rng.uniform(0, maze.width), rng.uniform(0, maze.height)) for _ in range(count)
    ]
    kinds = list(Region)
    rng.shuffle(kinds)
    out = {}
    for x, z in maze.cells():
        nearest = min(
            range(count),
            key=lambda i: (seeds[i][0] - x - 0.5) ** 2 + (seeds[i][1] - z - 0.5) ** 2,
        )
        out[(x, z)] = kinds[nearest % len(kinds)]
    return out


def _walls_by_cell(maze: Maze) -> dict[Cell, list[Segment]]:
    """The walls bounding each cell. A wall has a face in each cell beside
    it that lies inside the maze."""
    out: dict[Cell, list[Segment]] = {cell: [] for cell in maze.cells()}
    for wall in maze.walls:
        (x0, z0), (x1, _) = wall
        x, z = int(x0), int(z0)
        beside = [(x - 1, z), (x, z)] if x0 == x1 else [(x, z - 1), (x, z)]
        for cell in beside:
            if cell in out:
                out[cell].append(wall)
    return out
