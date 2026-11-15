# SPDX-License-Identifier: GPL-3.0-or-later
"""The QADE launcher: one window, a menu of games, and back again on quit."""

from grizzly_depths import GAME as GRIZZLY_DEPTHS
from qade_engine import GameDefinition, GameInfo, Services

from .launcher import Launcher, LauncherMemory

GAMES: tuple[GameDefinition, ...] = (GRIZZLY_DEPTHS,)

INFO = GameInfo(
    id="qade_launcher",
    title="QADE Launcher",
    package=__name__,
    description="Pick a game.",
)


_MEMORY = LauncherMemory()


def _create(services: Services) -> Launcher:
    return Launcher(services, GAMES, _MEMORY)


LAUNCHER = GameDefinition(INFO, _create)


def main() -> None:
    """Open the launcher. Quitting a game returns here; quitting here exits."""
    from qade_engine import run

    run(LAUNCHER, home=LAUNCHER)
