# SPDX-License-Identifier: GPL-3.0-or-later
"""Grizzly Depths' rules as the game runs them."""

import random
from math import cos, radians, sin

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from support import to_playing

from grizzly_depths import config, controls, sounds
from grizzly_depths.controls import Action
from grizzly_depths.game import CAUGHT_DISTANCE, GrizzlyDepths
from grizzly_depths.maze import DIRECTIONS
from qade_engine import Phase
from qade_engine.graphics import Viewport
from qade_engine.host.app import Frame
from qade_engine.input.bindings import DeviceState
from qade_engine.perf import PerfStats


@pytest.fixture
def game(services, store) -> GrizzlyDepths:
    g = GrizzlyDepths(services, high_score_store=store)
    g.rng = random.Random(0)
    g.reset()
    to_playing(g)
    g.level.bear.speed = 0.0
    return g


def hold(game: GrizzlyDepths, *actions: Action, seconds: float = 0.0) -> None:
    """Hold ``actions`` (and nothing else) for ``seconds``, but at least one
    step, the way the host feeds input: presses appear in one step, then are
    cleared."""
    game.actions.apply({action: 1.0 for action in actions})
    for _ in range(max(1, round(seconds * game.tick_hz))):
        game.step(game.dt)
        game.actions.clear_presses()


def stand_on_exit(game: GrizzlyDepths) -> None:
    game.cell = game.level.exit


# ---- moving -----------------------------------------------------------------


def test_held_turn_turns_once(game: GrizzlyDepths) -> None:
    facing = game.facing
    hold(game, Action.TURN_RIGHT, seconds=1.0)
    assert game.facing == facing + 1
    hold(game)
    hold(game, Action.TURN_LEFT, seconds=1.0)
    assert game.facing == facing


def test_held_walk_repeats_and_walls_block(game: GrizzlyDepths) -> None:
    m = game.level.maze
    cell, way = next(
        (c, d)
        for c in m.cells()
        for d in m.open_directions(c)
        if m.is_open(m.step(c, d), d)  # a straight run of two
    )
    game.cell, game.facing, game.cooldown = cell, way, 0.0
    hold(game, Action.FORWARD, seconds=config.STEP_TIME + 2 * game.dt)
    assert game.cell == m.step(m.step(cell, way), way)

    # Facing a wall: holding forward goes nowhere.
    start = game.level.start
    blocked = next(d for d in range(4) if not m.is_open(start, d))
    game.cell, game.facing, game.cooldown = start, blocked, 0.0
    hold(game, Action.FORWARD, seconds=1.0)
    assert game.cell == start


def test_tap_between_steps_is_buffered(game: GrizzlyDepths) -> None:
    game.cooldown = 0.1
    facing = game.facing
    hold(game, Action.TURN_LEFT)  # pressed and released while still cooling down
    hold(game, seconds=0.2)
    assert game.facing == facing - 1


# ---- attuning and descending ------------------------------------------------


def test_charge_fills_drains_and_clears(game: GrizzlyDepths) -> None:
    stand_on_exit(game)
    hold(game, Action.ATTUNE, seconds=1.0)
    charged = game.charge
    assert charged == pytest.approx(1.0 / config.attune_time(1), abs=0.02)

    hold(game)  # let go: it drains
    assert 0.0 < game.charge < charged

    game.cell = game.level.start  # step off: it is lost
    hold(game)
    assert game.charge == 0.0


def test_full_charge_scores_and_descends_one_level(game: GrizzlyDepths) -> None:
    stand_on_exit(game)
    hold(game, Action.ATTUNE, seconds=config.attune_time(1) + 0.1)
    assert game.score == config.EXIT_SCORE
    assert game.descent is not None and game.level.number == 1

    hold(game, seconds=config.LEVEL_FADE_TIME)
    assert game.descent is None
    assert game.level.number == 2
    assert game.cell == game.level.start
    assert game.phase is Phase.PLAYING

    # Deeper exits are worth more.
    game.level.bear.speed = 0.0
    stand_on_exit(game)
    hold(game, Action.ATTUNE, seconds=config.attune_time(2) + 0.1)
    assert game.score == config.EXIT_SCORE * (1 + 2)


# ---- being caught -----------------------------------------------------------


def test_bear_on_your_cell_ends_the_run_facing_it(game: GrizzlyDepths) -> None:
    """Caught dead centre by a bear that never moved: no divide by zero, and
    the bear stands where you were looking, so the view doesn't turn, even
    after you have spun round twice."""
    game.facing += 8
    game.camera_yaw = game.facing * 90.0
    bear = game.level.bear
    bear.cell = bear.next = bear.came_from = game.cell
    bear.progress = 0.0
    hold(game)
    assert game.phase is Phase.GAME_OVER

    dx, dz = DIRECTIONS[game.facing % 4]
    px, pz = game.cell[0] + 0.5, game.cell[1] + 0.5
    assert game.caught_bear == pytest.approx(
        (px + dx * CAUGHT_DISTANCE, pz + dz * CAUGHT_DISTANCE)
    )
    assert game.caught_yaw == pytest.approx(game.camera_yaw)


def test_caught_dead_centre_turns_to_the_way_the_bear_came(
    game: GrizzlyDepths,
) -> None:
    bear, m = game.level.bear, game.level.maze
    way = m.open_directions(game.cell)[0]
    game.facing = way + 1  # looking elsewhere, so the view must turn
    game.camera_yaw = game.facing * 90.0
    bear.cell = bear.next = game.cell
    bear.came_from = m.step(game.cell, way)
    bear.progress = 0.0
    hold(game)
    assert game.phase is Phase.GAME_OVER

    dx, dz = DIRECTIONS[way]
    px, pz = game.cell[0] + 0.5, game.cell[1] + 0.5
    assert game.caught_bear == pytest.approx(
        (px + dx * CAUGHT_DISTANCE, pz + dz * CAUGHT_DISTANCE)
    )
    yaw = radians(game.caught_yaw)
    assert (sin(yaw), cos(yaw)) == pytest.approx((dx, dz), abs=1e-9)


# ---- drawing ----------------------------------------------------------------


def draw(game: GrizzlyDepths) -> None:
    image = QImage(800, 600, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    view = Viewport(800, 600, 1.0)
    game.draw(Frame(painter, view, now=0.0, alpha=0.5, perf=PerfStats()))
    painter.end()


def test_every_screen_draws(game: GrizzlyDepths) -> None:
    draw(game)
    stand_on_exit(game)
    hold(game, Action.ATTUNE, seconds=0.5)
    draw(game)  # charging
    hold(game, Action.ATTUNE, seconds=config.attune_time(1))
    draw(game)  # descending
    hold(game, seconds=config.LEVEL_FADE_TIME)
    bear = game.level.bear
    bear.cell = bear.next = bear.came_from = game.cell
    hold(game)
    draw(game)  # mauled
    hold(game, seconds=GrizzlyDepths.GAME_OVER_DELAY + 0.1)
    draw(game)  # game over panel


# ---- sounds and controls ----------------------------------------------------


def test_heartbeat_only_within_reach_and_quickens() -> None:
    assert sounds.heartbeat_interval(config.APPROACH_DISTANCE + 1) is None
    beats = [sounds.heartbeat_interval(d) for d in range(config.APPROACH_DISTANCE + 1)]
    assert beats == sorted(beats) and beats[0] < beats[-1]


def test_every_action_has_a_key() -> None:
    every_key_held = DeviceState(keys=frozenset(map(int, Qt.Key)))
    strengths = controls.input_map().evaluate(every_key_held)
    assert [action for action in Action if not strengths.get(action)] == []
