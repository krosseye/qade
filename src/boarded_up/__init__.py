# SPDX-License-Identifier: GPL-3.0-or-later
from qade_engine import GameDefinition, GameInfo, Services

INFO = GameInfo(
    id="boarded_up",
    title="Boarded Up",
    package=__name__,
    description="Hold the house. Board the windows. Keep moving.",
    accent="#80de54",
)


def _create(services: Services):
    from .game import BoardedUp

    return BoardedUp(services)


GAME = GameDefinition(INFO, _create)


def main() -> None:
    """Play Boarded Up in its own window."""
    from qade_engine import run

    run(GAME)
