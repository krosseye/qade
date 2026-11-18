# SPDX-License-Identifier: GPL-3.0-or-later
"""Wayfinding: what the tunnels show to help you find your way."""

import random

from grizzly_depths.level import build_level
from grizzly_depths.render.dungeon import CLAW_REACH, _clawed, _facing_side


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
