# SPDX-License-Identifier: GPL-3.0-or-later
"""Laying out a level: the maze, where the player starts, the exit, the bear."""

import random
from dataclasses import dataclass

from . import config
from .bear import Bear
from .maze import Cell, Maze


@dataclass
class Level:
    number: int
    maze: Maze
    start: Cell
    facing: int
    exit: Cell
    bear: Bear
    to_lair: dict[Cell, int]


EXIT_REACH = 0.7  # the exit is at least this far from the start
START_GAP = 0.4  # the lair is at least this far from the start,
EXIT_GAP = 0.3  # and this far from the exit, so the bear can't camp it


def build_level(number: int, rng: random.Random) -> Level:
    """Level ``number`` (from 1), drawn from ``rng``: the player starts in a
    corner facing an open way, the exit is a random cell far from the start
    by path, and the bear sleeps clear of both, most likely on the way."""
    size = config.maze_size(number)
    maze = Maze(size, size, rng, config.LOOP_FRACTION, config.braid(number))

    start = rng.choice([(0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)])
    from_start = maze.distances(start)
    farthest = max(from_start.values())
    exit_cell = rng.choice(
        [cell for cell in maze.cells() if from_start[cell] >= EXIT_REACH * farthest]
    )

    from_exit = maze.distances(exit_cell)
    route = from_start[exit_cell]
    start_gap, exit_gap = int(START_GAP * farthest), int(EXIT_GAP * farthest)
    lairs = [
        cell
        for cell in maze.cells()
        if from_start[cell] >= start_gap and from_exit[cell] >= exit_gap
    ]
    weights = [
        1 / (4 + abs(from_start[c] - route / 2) + from_start[c] + from_exit[c] - route)
        for c in lairs
    ]
    bear = Bear(
        maze,
        rng.choices(lairs, weights)[0],
        speed=config.bear_speed(number),
        wake_delay=config.wake_delay(number),
        scent_range=config.scent_range(number),
        drift=config.drift(number),
        prowl_pace=config.prowl_pace(number),
        rng=rng,
    )
    return Level(
        number=number,
        maze=maze,
        start=start,
        facing=rng.choice(maze.open_directions(start)),
        exit=exit_cell,
        bear=bear,
        to_lair=maze.distances(bear.cell),
    )
