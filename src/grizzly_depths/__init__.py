# SPDX-License-Identifier: GPL-3.0-or-later
"""Grizzly Depths: a first-person maze chase on the QADE engine.

Inspired by 3D Monster Maze, 3-Demon, Tunnel Runner and Dungeons of
Daggorath: a pseudo-3D wireframe dungeon, an exit to find, and a bear that
hunts you through the halls.
"""

from qade_engine import GameDefinition, GameInfo, Services

INFO = GameInfo(
    id="grizzly_depths",
    title="Grizzly Depths",
    package=__name__,
    description="Find the way out of the maze. Something is hunting you.",
    accent="#9678ff",
)


def _create(services: Services):
    from .game import GrizzlyDepths

    return GrizzlyDepths(services)


GAME = GameDefinition(INFO, _create)


def main() -> None:
    """Play Grizzly Depths in its own window."""
    from qade_engine import run

    run(GAME)
