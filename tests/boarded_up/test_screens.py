# SPDX-License-Identifier: GPL-3.0-or-later
import random

import pytest
from PySide6.QtGui import QImage, QPainter
from support import painter_geometry, run_for

from boarded_up.game import BoardedUp
from boarded_up.sim import FIRST_LULL, WINDUP_TIME, Zombie, ZombieState, outside_spot
from qade_engine import Event, Phase
from qade_engine.graphics import Viewport
from qade_engine.host.app import Frame
from qade_engine.perf import PerfStats


@pytest.fixture
def game(services, store) -> BoardedUp:
    g = BoardedUp(services, high_score_store=store)
    g.rng = random.Random(0)
    g.reset()
    return g


def draw(game: BoardedUp, now: float = 0.15) -> None:
    image = QImage(800, 600, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    before = painter_geometry(painter)
    view = Viewport(800, 600, 1.0)
    game.draw(Frame(painter, view, now=now, alpha=0.5, perf=PerfStats()))
    assert painter_geometry(painter) == before
    painter.end()


def confirm(game: BoardedUp) -> None:
    assert game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)


def test_every_screen_draws(game: BoardedUp) -> None:
    draw(game)  # standby
    confirm(game)
    assert game.phase is Phase.INTRO
    draw(game)
    confirm(game)
    assert game.phase is Phase.PLAYING

    run_for(game, FIRST_LULL + 0.1)
    sim = game.sim
    assert sim.round == 1
    sim.zombies.clear()
    sim.points = 100_000  # every reachable door affordable
    window = next(w for w in sim.house.windows if w.room == sim.house.start)
    window.planks = 2
    sim.x, sim.y = window.inside[0] + 0.5, window.inside[1] + 0.5
    tearing = Zombie(*outside_spot(window, 0), 5, window, timer=0.1)
    queued = Zombie(*outside_spot(window, 1), 5, window)
    swiping = Zombie(sim.x + 0.6, sim.y, 5, None, state=ZombieState.CHASING)
    swiping.windup = WINDUP_TIME
    sim.zombies += [tearing, queued, swiping]
    draw(game)  # round banner, board-up prompt, a swipe winding up

    sim.zombies.clear()
    sim.to_spawn = 0
    game.round_time = 5.0
    assert sim.between_rounds
    draw(game)  # round survived

    game.died()
    draw(game)  # the house falling
    run_for(game, game.GAME_OVER_DELAY + 0.1)
    assert game.phase is Phase.GAME_OVER
    draw(game)  # game over panel
