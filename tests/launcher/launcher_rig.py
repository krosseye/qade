# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher test doubles: a rig around a Launcher, fake sounds and fake games."""

import math
from dataclasses import replace

import pytest
from PySide6.QtGui import QImage, QPainter
from support import QUIET

from qade_engine import GameDefinition, GameInfo, Services
from qade_engine.graphics import Camera, Viewport
from qade_engine.host.app import Frame
from qade_engine.input.state import ActionState
from qade_engine.perf import PerfStats
from qade_launcher import launcher as launcher_module
from qade_launcher.launcher import (
    LAUNCH_TIME,
    TICK_HZ,
    Launcher,
    LauncherMemory,
)

DT = 1.0 / TICK_HZ
VIEW = Viewport(800, 600, 1.0)


class SoundRecorder:
    """Stands in for the SoundBus: records plays and closes."""

    def __init__(self) -> None:
        self.played: list[tuple[str, int | None]] = []
        self.closed = 0

    def play(self, name: str, step: int | None = None) -> None:
        self.played.append((name, step))

    def close(self) -> None:
        self.closed += 1

    def names(self) -> list[str]:
        return [name for name, _ in self.played]


def games(count: int, accent: str = "") -> list[GameDefinition]:
    def create(services):  # never called: launching only asks the host
        raise AssertionError("the launcher must not build games itself")

    return [
        GameDefinition(
            GameInfo(f"g{i}", f"Game {i}", "qade_engine", accent=accent), create
        )
        for i in range(count)
    ]


class Rig:
    """A launcher with fake held input, a launch log and recorded sounds."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        count: int = 5,
        selected: int = 0,
        sound: bool = True,
    ) -> None:
        self.state = ActionState()
        self.launched: list[GameDefinition] = []
        self.sounds = SoundRecorder()
        monkeypatch.setattr(launcher_module, "open_bus", lambda register: self.sounds)
        self.memory = LauncherMemory(selected)
        self.games = games(count)
        self.services = Services(
            actions=self.state,
            settings=replace(QUIET, sound_effects=sound),
            launch=self.launched.append,
        )
        self.app = Launcher(self.services, self.games, self.memory)
        self.app.start()

    def press(self, action: str) -> None:
        """A fresh press: held from now on, and delivered like the host does."""
        self.state.apply({action: 1.0})
        self.app.on_action(action)

    def release(self) -> None:
        self.state.apply({})

    def run(self, seconds: float) -> None:
        for _ in range(round(seconds * TICK_HZ)):
            self.app.step(DT)

    def steps(self, count: int) -> None:
        for _ in range(count):
            self.app.step(DT)

    def until_handed_over(self) -> None:
        """Steps a launch to the exact tick it asks the host for the game."""
        before = len(self.launched)
        for _ in range(math.ceil(LAUNCH_TIME * TICK_HZ) + 2):
            self.app.step(DT)
            if len(self.launched) > before:
                return
        raise AssertionError("the launch never handed over")


def snapshot(app: Launcher) -> tuple:
    return (
        app.selected,
        app.pose,
        app.fade,
        app._previous,
        app._velocity,
        app._held,
        app._repeat_timer,
        app._launch_from,
        app._launch_progress,
    )


def draw(
    app: Launcher, image: QImage, alpha: float = 1.0, view: Viewport = VIEW
) -> None:
    painter = QPainter(image)
    app.draw(Frame(painter, view, now=0.0, alpha=alpha, perf=PerfStats()))
    painter.end()


def camera(pose) -> Camera:
    return Camera(pose, focal=480.0, center_x=400.0, horizon=264.0)
