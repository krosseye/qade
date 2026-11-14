# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher launching: timing, ignored input, fades and recovery."""

import itertools
import math

import pytest
from launcher_rig import DT, Rig

from qade_engine.input import UIAction
from qade_launcher import sounds
from qade_launcher.controls import Action
from qade_launcher.launcher import (
    FADE_IN_TIME,
    LAUNCH_TIME,
    TICK_HZ,
)


def test_launch_happens_once_and_only_after_the_full_launch_time(rig):
    rig.press(Action.NEXT)
    rig.release()
    rig.press(UIAction.CONFIRM)
    rig.release()
    rig.steps(math.floor(LAUNCH_TIME * TICK_HZ) - 1)
    assert rig.launched == []
    rig.run(2.0)
    assert rig.launched == [rig.games[1]]


def test_launch_sounds_play_once(rig):
    rig.press(UIAction.CONFIRM)
    rig.run(LAUNCH_TIME)
    assert rig.sounds.names() == [sounds.COIN, sounds.POWER_UP]


def test_input_while_launching_is_ignored(rig):
    rig.press(UIAction.CONFIRM)
    rig.steps(3)
    before = rig.sounds.played[:]
    rig.press(Action.NEXT)
    rig.press(Action.PREVIOUS)
    rig.press(UIAction.CONFIRM)
    rig.steps(math.ceil(LAUNCH_TIME * TICK_HZ) - 3)
    assert rig.app.selected == 0
    assert rig.launched == [rig.games[0]]
    assert rig.sounds.played == before


def test_confirming_mid_walk_launches_the_cabinet_being_walked_to(monkeypatch):
    rig = Rig(monkeypatch, count=6)
    for _ in range(3):
        rig.press(Action.NEXT)
        rig.release()
    rig.steps(2)
    rig.press(UIAction.CONFIRM)
    rig.run(LAUNCH_TIME + 0.1)
    assert rig.launched == [rig.games[3]]


def test_one_huge_step_still_launches_exactly_once(rig):
    rig.press(UIAction.CONFIRM)
    rig.app.step(5.0)
    rig.app.step(5.0)
    assert rig.launched == [rig.games[0]]
    assert 0.0 <= rig.app.fade <= 1.0


def test_the_launch_fade_only_darkens_and_ends_black(rig):
    rig.run(FADE_IN_TIME * 0.3)
    rig.press(UIAction.CONFIRM)
    fades = [rig.app.fade]
    for _ in range(math.ceil(LAUNCH_TIME * TICK_HZ)):
        rig.app.step(DT)
        fades.append(rig.app.fade)
        if rig.launched:
            break
    assert all(b >= a for a, b in itertools.pairwise(fades))
    assert fades[-1] == 1.0


def test_a_launch_the_host_never_carries_out_leaves_a_working_launcher(rig):
    rig.press(UIAction.CONFIRM)
    rig.run(LAUNCH_TIME + 0.1)
    assert rig.launched and not rig.app.launching
    rig.run(FADE_IN_TIME * 2 + 1.0)
    assert rig.app.fade == 0.0
    assert rig.app.pose.z == pytest.approx(rig.app._rest_pose(0).z, abs=1e-2)
    rig.press(Action.NEXT)
    assert rig.app.selected == 1
    rig.release()
    rig.press(UIAction.CONFIRM)
    rig.run(LAUNCH_TIME + 0.1)
    assert rig.launched == [rig.games[0], rig.games[1]]


def test_with_no_games_nothing_launches_and_nothing_moves(monkeypatch):
    rig = Rig(monkeypatch, count=0)
    rest = rig.app.pose
    for action in (UIAction.CONFIRM, Action.NEXT, Action.PREVIOUS):
        rig.press(action)
        rig.run(1.0)
        rig.release()
    assert rig.launched == []
    assert not rig.app.launching
    assert rig.app.selected == 0
    assert rig.app.pose == rest
