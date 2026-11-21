# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher layout: units in the aisle, cabinet geometry and camera framing."""

import math

import pytest
from launcher_rig import VIEW, Rig, camera, games
from PySide6.QtGui import QColor

from qade_engine.graphics import current_theme
from qade_engine.input import UIAction
from qade_launcher.cabinet import (
    BACK,
    PIVOT_DEPTH,
    PROFILE,
    SCREEN,
    SCREEN_CENTER,
    Cabinet,
)
from qade_launcher.launcher import (
    LAUNCH_DISTANCE,
)
from qade_launcher.units import OFFLINE_ACCENT, build_units, offline_units, side


@pytest.mark.parametrize("count", range(10))
def test_the_aisle_always_ends_level_with_three_or_four_dark_cabinets(count):
    offline = offline_units(count)
    assert offline in (3, 4)
    assert (count + offline) % 2 == 0


@pytest.mark.parametrize("count", [0, 1, 4, 7])
def test_units_keep_game_order_alternate_sides_and_put_offline_last(count):
    listed = games(count)
    units = build_units(listed)
    assert [unit.game for unit in units[:count]] == listed
    assert all(unit.game is None and unit.cabinet.offline for unit in units[count:])
    assert not any(unit.cabinet.offline for unit in units[:count])
    zs = [unit.cabinet.z for unit in units]
    assert zs == sorted(zs) and len(set(zs)) == len(zs)
    for index, unit in enumerate(units):
        assert math.copysign(1, unit.cabinet.x) == side(index)
        assert math.copysign(1, unit.cabinet.yaw) == side(index)


def test_cabinet_accents_follow_the_game_then_the_theme_then_offline():
    red = games(1, accent="#ff0000")[0]
    plain = games(1)[0]
    units = build_units([red, plain])
    assert units[0].cabinet.accent == QColor("#ff0000")
    assert units[1].cabinet.accent == current_theme().accent
    assert units[2].cabinet.accent == OFFLINE_ACCENT


def test_an_unparseable_accent_is_rejected_by_the_engine():
    with pytest.raises(ValueError, match="not a color"):
        games(1, accent="not-a-colour")


@pytest.mark.parametrize("yaw", [-45.0, 0.0, 30.0, 45.0, 180.0])
def test_cabinets_turn_rigidly_about_their_pivot(yaw):
    cabinet = Cabinet(2.0, 5.0, yaw, QColor("red"), {})
    assert cabinet.world(0.0, 1.0, PIVOT_DEPTH) == pytest.approx((2.0, 1.0, 5.0))
    corners = [(x, y, z) for z, y in PROFILE for x in (-0.6, 0.6)]
    for a in corners:
        for b in corners:
            local = math.dist(a, b)
            assert math.dist(cabinet.world(*a), cabinet.world(*b)) == pytest.approx(
                local
            )


@pytest.mark.parametrize("selected", [0, 1, 2, 3])
def test_launching_ends_square_in_front_of_the_selected_screen(monkeypatch, selected):
    rig = Rig(monkeypatch, count=4, selected=selected)
    rig.press(UIAction.CONFIRM)
    rig.until_handed_over()
    cabinet = rig.app.units[selected].cabinet
    view = camera(rig.app.pose).to_view(cabinet.world(*SCREEN_CENTER))
    assert view == pytest.approx((0.0, 0.0, LAUNCH_DISTANCE), abs=1e-6)


@pytest.mark.parametrize("selected", [0, 1, 2, 3])
def test_at_rest_the_selected_screen_faces_the_camera_and_is_in_view(
    monkeypatch, selected
):
    rig = Rig(monkeypatch, count=4, selected=selected)
    app = rig.app
    cam = camera(app.pose)
    cabinet = app.units[selected].cabinet
    eye = (app.pose.x, app.pose.y, app.pose.z)

    center = cam.project(cabinet.world(*SCREEN_CENTER))
    assert center is not None
    assert 0 < center.x() < VIEW.width and 0 < center.y() < VIEW.height

    def facing(index: int) -> bool:
        z0, y0 = PROFILE[index]
        z1, y1 = PROFILE[(index + 1) % len(PROFILE)]
        points = [cabinet.world(x, y, z) for x, y, z in ((0, y0, z0), (0, y1, z1))]
        normal = cabinet._direction(0, z1 - z0, -(y1 - y0))
        return cabinet._face(eye, index, points, normal)[0] >= 0

    assert facing(SCREEN)
    assert not facing(BACK)
