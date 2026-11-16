# SPDX-License-Identifier: GPL-3.0-or-later
"""Laying out a level: the maze, where the player starts, the exit, the bear."""

import random
from dataclasses import dataclass
from math import hypot

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


def build_level(number: int, rng: random.Random) -> Level:
    """Level ``number`` (from 1), drawn from ``rng``: the player starts in a
    corner facing an open way, the exit is the cell furthest from the start
    by path, and the bear sleeps near the centre."""
    size = config.maze_size(number)
    maze = Maze(size, size, rng, config.LOOP_FRACTION, config.braid(number))

    start = rng.choice([(0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)])
    from_start = maze.distances(start)
    exit_cell = max(from_start, key=from_start.__getitem__)

    from_exit = maze.distances(exit_cell)
    middle = (size - 1) / 2
    lairs = [
        cell
        for cell in maze.cells()
        if hypot(cell[0] - middle, cell[1] - middle) <= size / 4
        and from_exit[cell] >= 3
    ]
    bear = Bear(
        maze,
        rng.choice(lairs),
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
    )
