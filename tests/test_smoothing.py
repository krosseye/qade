# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from PySide6.QtCore import QPointF, QRectF, QSizeF

from qade_engine.graphics import Pose, Smoothed
from qade_engine.graphics.smoothing import interpolate


class Ticks:
    def __init__(self):
        self.count = 0

    def __call__(self) -> int:
        return self.count


@pytest.fixture
def ticks() -> Ticks:
    return Ticks()


def test_a_moved_value_slides_from_last_steps(ticks):
    x = Smoothed(0.0, ticks)
    ticks.count += 1
    x.set(10.0)
    assert [x.at(a) for a in (0.0, 0.25, 1.0)] == [0.0, 2.5, 10.0]


def test_only_the_first_set_in_a_step_keeps_where_it_was(ticks):
    x = Smoothed(0.0, ticks)
    ticks.count += 1
    x.set(10.0)
    x.set(8.0)
    assert x.at(0.5) == 4.0


def test_a_value_nothing_moved_this_step_draws_still(ticks):
    x = Smoothed(0.0, ticks)
    ticks.count += 1
    x.set(10.0)
    ticks.count += 1
    assert x.at(0.0) == x.at(0.5) == 10.0


def test_a_jump_never_slides(ticks):
    x = Smoothed(0.0, ticks)
    ticks.count += 1
    x.jump(500.0)
    assert x.at(0.0) == 500.0
    x.set(510.0)
    assert x.at(0.5) == 505.0


@pytest.mark.parametrize(
    ("start", "end", "half"),
    [
        (0, 10, 5),
        ((0.0, 2.0), (4.0, 6.0), (2.0, 4.0)),
        (QPointF(0, 0), QPointF(4, 8), QPointF(2, 4)),
        (QSizeF(2, 2), QSizeF(4, 6), QSizeF(3, 4)),
        (QRectF(0, 0, 2, 2), QRectF(4, 8, 4, 2), QRectF(2, 4, 3, 2)),
    ],
)
def test_interpolate_handles_the_kinds_games_move(start, end, half):
    assert interpolate(start, end, 0.5) == half


def test_interpolate_uses_a_lerp_method(ticks):
    middle = interpolate(Pose(0, 0, 0, 0), Pose(2, 0, 4, 90), 0.5)
    assert (middle.x, middle.z, middle.yaw) == (1, 2, 45)
