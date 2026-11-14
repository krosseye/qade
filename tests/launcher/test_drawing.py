# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher drawing: no side effects, no leaked painter state, black hand-overs."""

import pytest
from launcher_rig import VIEW, Rig, draw, snapshot
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from support import blank_image, painter_geometry

from qade_engine.graphics import Viewport
from qade_engine.host.app import Frame
from qade_engine.input import UIAction
from qade_engine.perf import PerfStats
from qade_launcher.controls import Action
from qade_launcher.launcher import (
    FADE_IN_TIME,
    LAUNCH_TIME,
    Launcher,
)


def _launcher_in(monkeypatch, state: str, count: int) -> Launcher:
    rig = Rig(monkeypatch, count=count, selected=count - 1)
    match state:
        case "start":
            pass
        case "settled":
            rig.run(1.0)
        case "walking":
            rig.run(1.0)
            rig.press(Action.PREVIOUS)
            rig.steps(5)
        case "launching":
            rig.run(1.0)
            rig.press(UIAction.CONFIRM)
            rig.run(LAUNCH_TIME * 0.6)
        case "launched" if count:
            rig.press(UIAction.CONFIRM)
            rig.until_handed_over()
        case "launched":
            rig.press(UIAction.CONFIRM)
            rig.run(LAUNCH_TIME)
    return rig.app


@pytest.mark.parametrize(
    "state", ["start", "settled", "walking", "launching", "launched"]
)
@pytest.mark.parametrize("count", [0, 1, 2, 9])
@pytest.mark.parametrize(
    "view", [VIEW, Viewport(2400, 600, 1.0), Viewport(800, 3200, 1.0)]
)
@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_drawing_never_changes_the_simulation(monkeypatch, state, count, view, alpha):
    app = _launcher_in(monkeypatch, state, count)
    before = snapshot(app)
    draw(app, blank_image(200, 150), alpha=alpha, view=view)
    assert snapshot(app) == before


@pytest.mark.parametrize("antialiased", [True, False])
@pytest.mark.parametrize("state", ["settled", "launching"])
def test_drawing_leaves_the_painter_as_it_found_it(monkeypatch, antialiased, state):
    app = _launcher_in(monkeypatch, state, 3)
    image = blank_image(400, 300)
    painter = QPainter(image)
    painter.translate(13, 7)
    painter.scale(0.5, 2.0)
    painter.setOpacity(0.6)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, antialiased)
    before = painter_geometry(painter)
    app.draw(Frame(painter, VIEW, now=0.0, alpha=0.5, perf=PerfStats()))
    after = painter_geometry(painter)
    painter.end()
    assert after == before


def _lit_pixels(image: QImage) -> int:
    lit = 0
    for x in range(0, image.width(), 8):
        for y in range(0, image.height(), 8):
            color = QColor(image.pixel(x, y))
            lit += max(color.red(), color.green(), color.blue()) > 8
    return lit


def test_the_first_frame_is_black_and_the_aisle_appears_after_the_fade(rig):
    first = blank_image(400, 300, QColor(Qt.GlobalColor.black))
    draw(rig.app, first, alpha=0.0)
    assert _lit_pixels(first) == 0

    rig.run(FADE_IN_TIME * 2)
    later = blank_image(400, 300, QColor(Qt.GlobalColor.black))
    draw(rig.app, later)
    assert _lit_pixels(later) > 20


def test_the_frame_is_black_when_the_launch_hands_over(rig):
    rig.run(1.0)
    rig.press(UIAction.CONFIRM)
    rig.until_handed_over()
    for alpha in (0.0, 1.0):
        image = blank_image(400, 300, QColor(Qt.GlobalColor.black))
        draw(rig.app, image, alpha=alpha)
        assert _lit_pixels(image) == 0
