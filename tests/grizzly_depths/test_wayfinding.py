# SPDX-License-Identifier: GPL-3.0-or-later
"""Wayfinding: what the tunnels show to help you find your way."""

import random

import pytest
from PySide6.QtGui import QColor, QImage, QPainter

from grizzly_depths.landmarks import (
    FEATURE_SPACING,
    NEAR_LAIR,
    Feature,
    Mark,
    Region,
    build_marks,
)
from grizzly_depths.level import build_level
from grizzly_depths.render.dungeon import CLAW_REACH, _clawed, _facing_side
from grizzly_depths.render.landmarks import draw_mark
from qade_engine.graphics import Camera, Pose


def test_claws_score_the_lairs_own_tunnels_only() -> None:
    level = build_level(3, random.Random(0))
    lair = level.bear.cell
    assert _clawed(level, lair)
    for cell, steps in level.to_lair.items():
        assert _clawed(level, cell) == (steps <= CLAW_REACH)
    assert not _clawed(level, (-1, 0))  # outside the maze


def test_a_wall_shows_the_face_of_the_cell_you_are_in() -> None:
    x, z = 2, 3
    east = ((x + 1, z), (x + 1, z + 1))
    assert _facing_side(east, x + 0.5, z + 0.5) == (x, z)
    assert _facing_side(east, x + 1.5, z + 0.5) == (x + 1, z)
    south = ((x, z + 1), (x + 1, z + 1))
    assert _facing_side(south, x + 0.5, z + 0.5) == (x, z)
    assert _facing_side(south, x + 0.5, z + 1.5) == (x, z + 1)


@pytest.mark.parametrize("seed", range(10))
def test_a_place_always_looks_the_same(seed: int) -> None:
    level = build_level(5, random.Random(seed))
    again = build_marks(level.maze, hash(tuple(level.maze.walls)), level.to_lair)
    assert level.marks == again


@pytest.mark.parametrize("seed", range(10))
def test_marks_sit_on_real_walls_and_keep_off_the_lair(seed: int) -> None:
    level = build_level(6, random.Random(seed))
    walls = set(level.maze.walls)
    for wall, cell in level.marks:
        assert wall in walls
        assert _facing_side(wall, cell[0] + 0.5, cell[1] + 0.5) == cell
        assert level.to_lair[cell] > NEAR_LAIR


@pytest.mark.parametrize("seed", range(10))
def test_features_are_spaced_apart_at_decision_points(seed: int) -> None:
    level = build_level(8, random.Random(seed))
    maze = level.maze
    cells = [cell for (_, cell), mark in level.marks.items() if mark.feature]
    for i, a in enumerate(cells):
        ways = maze.open_directions(a)
        assert not (len(ways) == 2 and ways[1] - ways[0] == 2)  # not a corridor
        near = maze.distances(a)
        for b in cells[i + 1 :]:
            assert near[b] >= FEATURE_SPACING


def test_every_kind_of_feature_and_region_turns_up() -> None:
    features, regions = set(), set()
    for seed in range(20):
        for mark in build_level(3, random.Random(seed)).marks.values():
            features.add(mark.feature)
            regions.add(mark.region)
    assert features - {None} == set(Feature)
    assert regions - {None} == {Region.CRACKS, Region.BRICK}  # bare shows nothing


@pytest.mark.parametrize(
    "mark",
    [Mark(region, None, 1) for region in (Region.CRACKS, Region.BRICK)]
    + [Mark(None, feature, 1) for feature in Feature],
)
@pytest.mark.parametrize("facing", [1, 3])  # from the west side, then the east
def test_every_mark_draws_from_either_side(mark: Mark, facing: int) -> None:
    image = QImage(160, 120, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0))
    wall = ((1, 0), (1, 1))
    cell = (0, 0) if facing == 1 else (1, 0)
    x = 0.3 if facing == 1 else 1.7
    camera = Camera(Pose(x, 0.5, 0.5, facing * 90.0), 100.0, 80.0, 60.0)
    painter = QPainter(image)
    draw_mark(painter, camera, wall, cell, mark, 1.0)
    painter.end()
    blank = QImage(image.size(), image.format())
    blank.fill(QColor(0, 0, 0))
    assert image != blank
