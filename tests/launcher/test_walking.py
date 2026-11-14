# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher walking: memory, ends of the aisle, held-key repeat, settling, fade-in."""

import itertools
import math

import pytest
from launcher_rig import DT, Rig, games
from support import QUIET

import qade_launcher
from qade_engine import Services
from qade_engine.input.state import ActionState
from qade_launcher import sounds
from qade_launcher.controls import Action
from qade_launcher.launcher import (
    FADE_IN_TIME,
    REPEAT_DELAY,
    REPEAT_INTERVAL,
    TICK_HZ,
    Launcher,
    LauncherMemory,
)


@pytest.mark.parametrize(
    ("remembered", "count", "expected"),
    [(7, 3, 2), (-4, 3, 0), (0, 0, 0), (5, 0, 0), (2, 3, 2)],
)
def test_a_stale_memory_is_clamped_into_the_game_list(
    monkeypatch, remembered, count, expected
):
    rig = Rig(monkeypatch, count=count, selected=remembered)
    assert rig.app.selected == expected


def test_returning_from_a_game_stands_at_the_same_cabinet_already_at_rest(rig):
    rig.press(Action.NEXT)
    rig.release()
    rig.press(Action.NEXT)
    rig.release()
    assert rig.memory.selected == 2

    again = Launcher(rig.services, rig.games, rig.memory)
    assert again.selected == 2
    assert again.pose == again._rest_pose(2)
    again.step(DT)
    assert again.pose.z == pytest.approx(again._rest_pose(2).z)


def test_the_packaged_launcher_shares_its_memory_between_instances(monkeypatch):
    monkeypatch.setattr(qade_launcher, "GAMES", tuple(games(4)))
    monkeypatch.setattr(qade_launcher, "_MEMORY", LauncherMemory())
    state = ActionState()
    services = Services(actions=state, settings=QUIET)

    first = qade_launcher.LAUNCHER.create(services)
    state.apply({Action.NEXT: 1.0})
    first.on_action(Action.NEXT)
    first.stop()

    second = qade_launcher.LAUNCHER.create(services)
    assert second.selected == 1


def test_walking_past_either_end_bumps_once_per_press_and_stays_put(monkeypatch):
    rig = Rig(monkeypatch, count=3, selected=0)
    rig.press(Action.PREVIOUS)
    rig.run(2.0)
    assert rig.app.selected == 0
    assert rig.sounds.names() == [sounds.END]

    rig.release()
    rig.steps(1)
    rig.press(Action.NEXT)
    rig.release()
    rig.press(Action.NEXT)
    rig.release()
    rig.press(Action.NEXT)
    rig.run(1.0)
    assert rig.app.selected == 2
    assert rig.sounds.names().count(sounds.END) == 2


def test_a_tap_walks_exactly_one_cabinet(rig):
    rig.press(Action.NEXT)
    rig.steps(math.floor(REPEAT_DELAY * TICK_HZ) - 1)
    rig.release()
    rig.run(1.0)
    assert rig.app.selected == 1


def test_holding_repeats_after_the_delay_then_at_the_interval_without_drift(
    monkeypatch,
):
    rig = Rig(monkeypatch, count=100)
    held = 10.0
    rig.press(Action.NEXT)
    rig.run(held)
    repeats = math.floor((held - REPEAT_DELAY) / REPEAT_INTERVAL) + 1
    assert rig.app.selected == 1 + repeats


def test_the_first_repeat_waits_for_the_full_delay(rig):
    rig.press(Action.NEXT)
    rig.steps(math.floor(REPEAT_DELAY * TICK_HZ))
    assert rig.app.selected == 1
    rig.steps(2)
    assert rig.app.selected == 2


def test_pressing_again_restarts_the_repeat_delay(rig):
    rig.press(Action.NEXT)
    rig.run(REPEAT_DELAY * 0.8)
    rig.release()
    rig.steps(1)
    rig.press(Action.NEXT)
    rig.run(REPEAT_DELAY * 0.8)
    assert rig.app.selected == 2


def test_switching_direction_while_held_follows_the_new_direction(monkeypatch):
    rig = Rig(monkeypatch, count=20, selected=10)
    rig.press(Action.NEXT)
    rig.run(1.0)
    peak = rig.app.selected
    rig.state.apply({Action.NEXT: 1.0, Action.PREVIOUS: 1.0})
    rig.app.on_action(Action.PREVIOUS)
    rig.run(1.0)
    assert rig.app.selected < peak - 1


def test_each_cabinet_chimes_its_note_and_the_scale_wraps(monkeypatch):
    rig = Rig(monkeypatch, count=12)
    for _ in range(11):
        rig.press(Action.NEXT)
        rig.release()
    notes = [step for name, step in rig.sounds.played if name == sounds.SELECT]
    scale = len(sounds.UNIT_SEMITONES)
    assert notes == [index % scale for index in range(1, 12)]
    assert all(0 <= note < scale for note in notes)


def test_a_walk_settles_on_the_cabinet_without_overshooting(rig):
    rig.press(Action.NEXT)
    rig.release()
    target = rig.app._rest_pose(1)
    zs = []
    for _ in range(TICK_HZ):
        rig.app.step(DT)
        zs.append(rig.app.pose.z)
    assert all(b >= a - 1e-9 for a, b in itertools.pairwise(zs))
    assert max(zs) <= target.z + 1e-9
    assert rig.app.pose.z == pytest.approx(target.z, abs=1e-2)
    assert rig.app.pose.x == pytest.approx(target.x, abs=1e-2)
    assert rig.app.pose.yaw == pytest.approx(target.yaw, abs=1e-1)


def test_the_fade_in_ends_at_clear_and_never_goes_negative(rig):
    assert rig.app.fade == 1.0
    rig.run(FADE_IN_TIME / 2)
    assert 0.0 < rig.app.fade < 1.0
    rig.run(FADE_IN_TIME * 3)
    assert rig.app.fade == 0.0
