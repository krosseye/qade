# SPDX-License-Identifier: GPL-3.0-or-later
"""Doubles and helpers shared by the suite. Fixtures live in ``conftest.py``."""

import math
from collections.abc import Callable

from PySide6.QtGui import QColor, QImage, QPainter

from qade_engine import ArcadeGame, Event, GameDefinition, GameInfo, Phase, Services
from qade_engine.host.app import Frame, HostSettings
from qade_engine.input import InputMap, add_ui_actions

QUIET = HostSettings(use_tts=False, sound_effects=False, music=False)

NASTY_FLOATS = (math.nan, math.inf, -math.inf, 1e308, -1e308, 5e-324, -0.0)


class FakeClock:
    """A ``perf_counter`` stand-in that only moves when a test says so."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeApp:
    """The smallest thing the host can run, recording every call into it.

    ``fail_in`` names a method that raises; ``on_step`` and ``on_draw`` let a
    test act from inside the app's own callbacks.
    """

    canvas_size = (800, 600)
    tick_hz = 64

    def __init__(self, services: Services, input_map: InputMap | None = None):
        self.services = services
        self.input_map = (
            input_map if input_map is not None else add_ui_actions(InputMap())
        )
        self.calls: list = []
        self.step_dts: list[float] = []
        self.fail_in: str | None = None
        self.on_step: Callable[[FakeApp], None] | None = None
        self.on_draw: Callable[[Frame], None] | None = None

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if name == self.fail_in:
            raise RuntimeError(f"boom in {name}")

    def start(self) -> None:
        self._record("start")

    def stop(self) -> None:
        self._record("stop")

    def suspend(self) -> None:
        self._record("suspend")

    def resume(self) -> None:
        self._record("resume")

    def step(self, dt: float) -> None:
        self.step_dts.append(dt)
        self._record("step")
        if self.on_step is not None:
            self.on_step(self)

    def on_action(self, action: str) -> None:
        self.calls.append(("action", action))

    def draw(self, frame: Frame) -> None:
        self._record("draw")
        if self.on_draw is not None:
            self.on_draw(frame)


def define(
    create: Callable[[Services], object], game_id: str = "fake"
) -> GameDefinition:
    """Wraps an app factory so ``Host.switch_to`` can launch it."""
    return GameDefinition(GameInfo(game_id, game_id.upper(), "qade_engine"), create)  # type: ignore[arg-type]


class ProbeGame(ArcadeGame):
    """An ``ArcadeGame`` that records its hooks, for flow and lifecycle tests."""

    INFO = GameInfo("probe", "Probe", "qade_engine")
    INTRO_LINES = ("LINE ONE", "LINE TWO")

    def setup(self) -> None:
        self.log: list = ["setup"]
        self.playing_steps = 0
        self.dts: list[float] = []

    def reset(self) -> None:
        self.log.append("reset")

    def step_playing(self, dt: float) -> None:
        self.playing_steps += 1
        self.dts.append(dt)

    def field_resized(self, grew_x: float, grew_y: float) -> None:
        self.log.append(("resized", grew_x, grew_y))


def run_for(game: ArcadeGame, seconds: float) -> None:
    """Steps a game the way the host does: whole fixed steps of ``game.dt``."""
    for _ in range(round(seconds * game.tick_hz)):
        game.step(game.dt)


def to_playing(game: ArcadeGame) -> None:
    """Drives a fresh game from standby, through the intro, into a settled run."""
    assert game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    assert game.phase is Phase.INTRO
    assert game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    assert game.phase is Phase.PLAYING and game.transition is None


def painter_geometry(painter: QPainter) -> tuple:
    """State a helper must never leak, because later draws inherit it silently."""
    return (
        painter.transform(),
        painter.worldMatrixEnabled(),
        painter.opacity(),
        painter.hasClipping(),
        painter.clipBoundingRect(),
        painter.compositionMode(),
        painter.renderHints(),
    )


def painter_style(painter: QPainter) -> tuple:
    """Pen, brush and font: may change in leaf helpers, never in screen helpers."""
    pen, brush = painter.pen(), painter.brush()
    return (
        pen.color().rgba(),
        pen.widthF(),
        pen.style(),
        pen.isCosmetic(),
        brush.color().rgba(),
        brush.style(),
        painter.font().toString(),
    )


SENTINEL = QColor(255, 0, 255)


def blank_image(width: int, height: int, fill: QColor = SENTINEL) -> QImage:
    """An image pre-filled with a sentinel colour, so 'not cleared' is visible."""
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(fill)
    return image
