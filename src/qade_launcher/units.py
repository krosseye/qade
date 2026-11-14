# SPDX-License-Identifier: GPL-3.0-or-later
"""The aisle's layout: one cabinet per game, alternating sides, then dark ones."""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial

from PySide6.QtGui import QColor

from qade_engine import GameDefinition
from qade_engine.graphics import current_theme

from . import art
from .cabinet import DOOR, MARQUEE, PANEL, SCREEN, Art, Cabinet

UNIT_SPACING = 3.2  # along the aisle between units, which alternate sides
CABINET_X = 1.8  # distance from the aisle's centre line
CABINET_YAW = 45.0  # degrees each cabinet turns towards the aisle
OFFLINE_ACCENT = QColor(90, 110, 125)


@dataclass(frozen=True)
class Unit:
    game: GameDefinition | None
    cabinet: Cabinet


def side(index: int) -> int:
    """Units alternate: left (-1), right (1), left..."""
    return -1 if index % 2 == 0 else 1


def offline_units(game_count: int) -> int:
    """Dark cabinets past the last game, so the aisle goes on: 3 or 4, making
    the total even so both sides of the aisle end level."""
    return 4 - game_count % 2


def build_units(games: Sequence[GameDefinition]) -> list[Unit]:
    """A unit per game, in order, then the offline ones."""
    units = []
    for index in range(len(games) + offline_units(len(games))):
        sign = side(index)
        game = games[index] if index < len(games) else None
        screen: Art
        if game is not None:
            info = game.info
            accent = QColor(info.accent) if info.accent else current_theme().accent
            title = info.title
            screen = partial(art.screen, title, accent.name())
        else:
            accent, title, screen = OFFLINE_ACCENT, "OUT OF ORDER", art.offline_screen
        name = accent.name()
        cabinet = Cabinet(
            x=sign * CABINET_X,
            z=index * UNIT_SPACING,
            yaw=sign * CABINET_YAW,
            accent=accent,
            art={
                MARQUEE: partial(art.marquee, title, name),
                SCREEN: screen,
                PANEL: partial(art.control_panel, name),
                DOOR: partial(art.coin_door, name),
            },
            offline=game is None,
        )
        units.append(Unit(game, cabinet))
    return units
