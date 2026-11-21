# SPDX-License-Identifier: GPL-3.0-or-later
"""QADE: a small engine for vector-style arcade games built on PySide6.

A game is a package that exports a ``GameDefinition``. Most games subclass
``ArcadeGame`` and only write their own world. ``run`` plays a game in its
own window.
"""

import os
import warnings

warnings.filterwarnings("ignore", "Using SDL2 binaries from pysdl2-dll")
# SDL otherwise turns SIGINT/SIGTERM into quit events nobody reads, so the
# game can't be stopped with Ctrl+C, kill, or logout.
os.environ.setdefault("SDL_NO_SIGNAL_HANDLERS", "1")

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
