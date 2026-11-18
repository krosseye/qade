# SPDX-License-Identifier: GPL-3.0-or-later
"""Grizzly Depths' core: mazes, levels, the bear, and simulated runs."""

import itertools
import random
from collections import Counter
from math import hypot

import pytest

from grizzly_depths import config
from grizzly_depths.bear import Bear, Mood
from grizzly_depths.level import EXIT_GAP, EXIT_REACH, START_GAP, build_level
from grizzly_depths.maze import Maze, opposite

DT = 1 / 64
SEEDS = range(20)


def maze(seed: int, size: int = 10, loops: float = 0.08, braid: float = 0.5) -> Maze:
    return Maze(size, size, random.Random(seed), loops, braid)


def openings(m: Maze) -> int:
    return sum(len(m.open_directions(c)) for c in m.cells()) // 2


# ---- maze -------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_maze_is_connected_symmetric_and_bounded(seed: int) -> None:
    m = maze(seed, size=3 + seed % 12)
    assert len(m.distances((0, 0))) == m.width * m.height
    for cell in m.cells():
        for d in m.open_directions(cell):
            nxt = m.step(cell, d)
            assert 0 <= nxt[0] < m.width and 0 <= nxt[1] < m.height
            assert m.is_open(nxt, opposite(d))


def test_same_seed_same_maze() -> None:
    assert maze(7).walls == maze(7).walls
    assert maze(7).walls != maze(8).walls


@pytest.mark.parametrize("seed", SEEDS)
def test_no_braid_no_loops_is_a_perfect_maze(seed: int) -> None:
    m = maze(seed, loops=0.0, braid=0.0)
    assert openings(m) == m.width * m.height - 1  # a spanning tree


def test_braiding_and_loops_open_more_walls() -> None:
    perfect = openings(maze(1, loops=0.0, braid=0.0))
    assert openings(maze(1, loops=0.0, braid=1.0)) > perfect
    assert openings(maze(1, loops=0.3, braid=0.0)) > perfect


@pytest.mark.parametrize("seed", SEEDS)
def test_no_wall_floats_free(seed: int) -> None:
    """Every wall segment touches another one: no lone stub hangs in mid-air.
    Free-standing pillars of two or more segments are fine, and common."""
    m = maze(seed, loops=0.5, braid=1.0)
    ends = Counter(point for segment in m.walls for point in segment)
    for a, b in m.walls:
        assert ends[a] > 1 or ends[b] > 1, (a, b)


def test_walls_match_openings() -> None:
    m = maze(3)
    size = m.width
    # Every interior edge is either open or a wall, plus the outer boundary.
    interior = 2 * size * (size - 1)
    assert len(m.walls) == interior - openings(m) + 4 * size


# ---- config -----------------------------------------------------------------


def test_difficulty_ramps_then_plateaus() -> None:
    levels = range(1, 40)
    for curve, rising in (
        (config.maze_size, True),
        (config.bear_speed, True),
        (config.scent_range, True),
        (config.drift, True),
        (config.prowl_pace, True),
        (config.attune_time, True),
        (config.wake_delay, False),
        (config.braid, False),
    ):
        values = [curve(n) for n in levels]
        pairs = list(itertools.pairwise(values))
        assert all(b >= a if rising else b <= a for a, b in pairs), curve.__name__
        assert values[0] != values[-1], f"{curve.__name__} never ramps"
        assert values[-1] == values[-2], f"{curve.__name__} never plateaus"
    assert config.maze_size(100) == config.MAX_MAZE_SIZE


# ---- level ------------------------------------------------------------------


@pytest.mark.parametrize("number", [1, 2, 5, 10, 15, 30])
@pytest.mark.parametrize("seed", range(5))
def test_level_layout(number: int, seed: int) -> None:
    level = build_level(number, random.Random(seed))
    m, size = level.maze, config.maze_size(number)
    assert (m.width, m.height) == (size, size)
    assert set(level.start) <= {0, size - 1}  # a corner
    assert m.is_open(level.start, level.facing)
    from_start = m.distances(level.start)
    farthest = max(from_start.values())
    assert from_start[level.exit] >= EXIT_REACH * farthest
    assert level.bear.mood is Mood.ASLEEP
    lair = level.bear.cell
    assert from_start[lair] >= int(START_GAP * farthest)
    assert m.distances(level.exit)[lair] >= max(3, int(EXIT_GAP * farthest))


# ---- bear -------------------------------------------------------------------


def bear_in(m: Maze, cell=(0, 0), wake_delay=1.0, scent=3, seed=0) -> Bear:
    return Bear(
        m,
        cell,
        speed=2.0,
        wake_delay=wake_delay,
        scent_range=scent,
        drift=0.5,
        prowl_pace=0.6,
        rng=random.Random(seed),
    )


def far_corner(m: Maze) -> tuple[int, int]:
    return (m.width - 1, m.height - 1)


def test_bear_sleeps_then_prowls() -> None:
    m = maze(0)
    bear = bear_in(m, wake_delay=1.0)
    for _ in range(int(0.9 / DT)):
        bear.step(DT, far_corner(m))
    assert bear.mood is Mood.ASLEEP and bear.cell == (0, 0)
    for _ in range(int(0.2 / DT)):
        bear.step(DT, far_corner(m))
    assert bear.mood is Mood.PROWLING


def test_chime_wakes_bear_rearing_then_hunting() -> None:
    m = maze(0)
    bear = bear_in(m, wake_delay=99.0)
    bear.step(DT, far_corner(m), chiming=True)
    assert bear.mood is Mood.REARING and bear.called
    for _ in range(int(config.REAR_TIME / DT) + 1):
        bear.step(DT, far_corner(m))
    assert bear.mood is Mood.HUNTING


def test_called_bear_comes_from_afar_then_hunts_by_scent() -> None:
    """The chime calls it from beyond scent range, and it keeps coming. Once
    it has closed within range it hunts by scent alone, so it loses the
    trail when the player gets far enough away."""
    m = maze(0, size=12)
    bear = bear_in(m, wake_delay=99.0, scent=3)
    target = far_corner(m)
    bear.step(DT, target, chiming=True)
    assert bear.path_distance > bear.scent_range + config.LOSE_MARGIN
    distances = []
    for _ in range(int(60 / DT)):
        if bear.path_distance > bear.scent_range:
            assert bear.hunting and bear.called, "lost the trail while called"
        bear.step(DT, target)
        distances.append(bear.path_distance)
        if bear.path_distance == 0:
            break
    assert distances[-1] == 0, "never reached the player"
    assert distances == sorted(distances, reverse=True)  # never backs off
    assert not bear.called
    # Teleport the player far away
    bear.step(DT, (0, 0))
    assert bear.path_distance > bear.scent_range + config.LOSE_MARGIN
    assert bear.mood is Mood.PROWLING


@pytest.mark.parametrize("seed", range(5))
def test_prowling_bear_only_turns_back_at_dead_ends(seed: int) -> None:
    m = maze(seed, size=12, braid=0.0)  # plenty of dead ends to turn back at
    bear = bear_in(m, wake_delay=0.0, scent=-1, seed=seed)  # never smells you
    visited = set()
    for _ in range(int(30 / DT)):
        was = bear.cell
        bear.step(DT, far_corner(m))
        visited.add(bear.cell)
        if bear.cell != was and bear.next == bear.came_from:
            assert len(m.open_directions(bear.cell)) == 1, bear.cell
    assert bear.mood is Mood.PROWLING
    assert len(visited) > 20  # it really roamed


@pytest.mark.parametrize("seed", range(5))
def test_approach_points_at_the_bear(seed: int) -> None:
    m = maze(seed)
    bear = bear_in(m, cell=far_corner(m))
    to_bear = m.distances(bear.cell)
    for cell in m.cells():
        way = bear.approach(cell)
        if cell == bear.cell:
            assert way is None
        else:
            assert m.is_open(cell, way)
            assert to_bear[m.step(cell, way)] == to_bear[cell] - 1


# ---- simulated runs ---------------------------------------------------------


class Run:
    """A level played headlessly by a bot, with a simplified copy of the
    game's rules (see ``GrizzlyDepths.step_playing``): turns fold into the
    step's cooldown, and a released charge drops at once. It checks balance
    and the bear; ``test_game.py`` checks the real rules."""

    def __init__(self, number: int, seed: int) -> None:
        self.level = build_level(number, random.Random(seed))
        self.cell, self.facing = self.level.start, self.level.facing
        self.time, self.charge = 0.0, 0.0
        self.cooldown = 0.0

    def touching(self) -> bool:
        bx, bz = self.level.bear.position
        return hypot(bx - self.cell[0] - 0.5, bz - self.cell[1] - 0.5) < (
            config.CATCH_DISTANCE
        )

    def caught(self) -> bool:
        return self.level.bear.mood is Mood.HUNTING and self.touching()

    def play(self, bot, limit: float = 600.0) -> str:
        bear = self.level.bear
        while self.time < limit:
            self.time += DT
            attuning = self._act(bot)
            if self.charge >= 1.0:
                return "escaped"
            was = bear.cell
            if self.touching():
                bear.startle()
            bear.step(DT, self.cell, chiming=attuning)
            # At these speeds it moves at most one cell per tick.
            assert bear.cell in {was} | self._neighbours(was), "through a wall"
            if self.caught():
                return "caught"
        return "timeout"

    def _neighbours(self, cell):
        m = self.level.maze
        return {m.step(cell, d) for d in m.open_directions(cell)}

    def _act(self, bot) -> bool:
        """Advance the player one tick; True while attuning on the crystal."""
        if self.cell == self.level.exit and bot(self) == "attune":
            self.charge += DT / config.attune_time(self.level.number)
            return True
        self.charge = 0.0
        self.cooldown -= DT
        if self.cooldown > 0:
            return False
        way = bot(self)
        if way is None or way == "attune":
            return False
        turns = min((way - self.facing) % 4, (self.facing - way) % 4)
        self.facing = way
        self.cell = self.level.maze.step(self.cell, way)
        self.cooldown = config.STEP_TIME + turns * config.TURN_TIME
        return False


def stand_still(run: Run):
    return None


def run_for_exit(run: Run):
    """Shortest path to the crystal, then attune."""
    if run.cell == run.level.exit:
        return "attune"
    m = run.level.maze
    to_exit = m.distances(run.level.exit)
    return min(m.open_directions(run.cell), key=lambda d: to_exit[m.step(run.cell, d)])


@pytest.mark.parametrize("seed", SEEDS)
def test_bear_always_finds_an_idle_player(seed: int) -> None:
    assert Run(5, seed).play(stand_still) == "caught"


@pytest.mark.parametrize("number", [1, 5, 10, 20])
@pytest.mark.parametrize("seed", range(10))
def test_bear_never_walks_through_walls(number: int, seed: int) -> None:
    """Over whole runs, prowling, hunting and chime-called, the bear only ever
    steps to an open neighbour. ``Run.play`` asserts it every tick."""
    Run(number, seed).play(run_for_exit)


def test_level_one_is_beatable_by_a_beeline() -> None:
    results = Counter(Run(1, seed).play(run_for_exit) for seed in range(100))
    assert results["escaped"] >= 60, results
