# SPDX-License-Identifier: GPL-3.0-or-later
"""QADE: a small engine for vector-style arcade games built on PySide6.

A game is a package that exports a ``GameDefinition``. Most games subclass
``ArcadeGame`` and only write their own world. ``run`` plays a game in its
own window.
"""

import warnings

warnings.filterwarnings("ignore", "Using SDL2 binaries from pysdl2-dll")

from .arcade import ArcadeGame, Event, Phase
from .host import App, Frame, GameDefinition, GameInfo, Services, run
from .persistence import HighScoreStore

__all__ = [
    "App",
    "ArcadeGame",
    "Event",
    "Frame",
    "GameDefinition",
    "GameInfo",
    "HighScoreStore",
    "Phase",
    "Services",
    "run",
]
