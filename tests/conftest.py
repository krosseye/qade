# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixtures: one headless QApplication, deterministic randomness, hosts and games."""

import os

# Before any PySide6 import, which reads it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import random
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication
from support import QUIET, FakeClock, ProbeGame

from qade_engine import HighScoreStore, Services
from qade_engine.host import host as host_module
from qade_engine.host.host import Host
from qade_engine.input import InputMap
from qade_engine.input.gamepad import NullGamepad
from qade_engine.input.manager import InputManager


@pytest.fixture(scope="session", autouse=True)
def qapp() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication(
        ["qade-tests", "--platform", "offscreen"]
    )
    assert isinstance(app, QApplication)
    yield app


@pytest.fixture(autouse=True)
def _seeded() -> None:
    random.seed(0x0A5CADE)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Freezes the host's wall clock; tests move it with ``clock.advance``."""
    fake = FakeClock()
    monkeypatch.setattr(host_module, "perf_counter", fake)
    return fake


@pytest.fixture
def input_manager() -> InputManager:
    return InputManager(InputMap(), gamepad_backend=NullGamepad())


@pytest.fixture
def host(clock: FakeClock, input_manager: InputManager) -> Iterator[Host]:
    h = Host(input_manager, QUIET, refresh_rate=60)
    # Tests call tick() and paint() by hand; live timers would race the fake clock.
    h._tick_timer.stop()
    h._frame_timer.stop()
    yield h
    h.shutdown()


@pytest.fixture
def store(tmp_path) -> HighScoreStore:
    """A high-score file in tmp, never ``~/.qade``."""
    return HighScoreStore(tmp_path / "probe" / "highscore.json")


@pytest.fixture
def services() -> Services:
    return Services(settings=QUIET)


@pytest.fixture
def game(services: Services, store: HighScoreStore) -> Iterator[ProbeGame]:
    g = ProbeGame(services, high_score_store=store)
    yield g
    g.stop()
