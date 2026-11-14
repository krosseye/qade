# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher sound lifecycle: off, unavailable, and closing."""

from launcher_rig import DT, Rig, games
from support import QUIET

from qade_engine import Services
from qade_engine.input import UIAction
from qade_launcher import launcher as launcher_module
from qade_launcher.controls import Action
from qade_launcher.launcher import (
    TICK_HZ,
    Launcher,
    LauncherMemory,
)


def test_sound_off_never_opens_a_bus(monkeypatch):
    def refuse(register):
        raise AssertionError("opened a sound bus with sound effects off")

    monkeypatch.setattr(launcher_module, "open_bus", refuse)
    app = Launcher(Services(settings=QUIET), games(2))
    app.start()
    app.on_action(UIAction.CONFIRM)
    app.stop()


def test_an_unavailable_bus_leaves_a_silent_working_launcher(monkeypatch):
    rig = Rig(monkeypatch)
    monkeypatch.setattr(launcher_module, "open_bus", lambda register: None)
    app = Launcher(rig.services, rig.games, LauncherMemory())
    app.start()
    rig.state.apply({Action.NEXT: 1.0})
    app.on_action(Action.NEXT)
    app.on_action(UIAction.CONFIRM)
    for _ in range(TICK_HZ * 2):
        app.step(DT)
    app.stop()
    assert rig.launched == [rig.games[1]]


def test_stop_closes_the_bus_once_even_when_called_twice(rig):
    rig.app.stop()
    rig.app.stop()
    assert rig.sounds.closed == 1
    rig.press(Action.NEXT)
    assert rig.sounds.names() == []
