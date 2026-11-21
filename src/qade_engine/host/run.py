# SPDX-License-Identifier: GPL-3.0-or-later
"""Runs a game from the command line in its own window."""

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLoggingCategory
from PySide6.QtWidgets import QApplication

from qade_engine.diagnostics import log_system_info
from qade_engine.persistence import SAVE_ROOT

from .app import GameDefinition, HostSettings
from .view import use_opengl_format
from .window import HostWindow

_log = logging.getLogger(__name__)


def start_logging() -> None:
    """Logs to the console, if there is one, and to ``~/.qade/qade.log``.

    Uncaught exceptions, including those raised inside Qt callbacks, are
    logged instead of printed.
    """
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"
            )
        )
        handlers.append(console)
    try:
        SAVE_ROOT.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                SAVE_ROOT / "qade.log",
                maxBytes=1_000_000,
                backupCount=1,
                encoding="utf-8",
            )
        )
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
    QLoggingCategory.setFilterRules("qt.multimedia.ffmpeg.info=false")
    sys.excepthook = lambda *exc_info: _log.critical(
        "uncaught exception", exc_info=exc_info
    )


def parse_settings(title: str) -> HostSettings:
    """Reads the host's settings from the command line.

    Args:
        title: The game's title, for the help text.

    Returns:
        The settings. A Steam Deck always starts fullscreen.
    """
    parser = argparse.ArgumentParser(description=f"Launch {title}.")
    parser.add_argument(
        "--fullscreen", action="store_true", help="Launch in fullscreen mode."
    )
    parser.add_argument(
        "--no-tts", action="store_true", help="Launch without text-to-speech intro."
    )
    parser.add_argument(
        "--no-sfx", action="store_true", help="Launch without sound effects."
    )
    parser.add_argument("--no-music", action="store_true", help="Launch without music.")
    parser.add_argument(
        "--software-renderer",
        action="store_true",
        help="Launch in software rendering mode.",
    )
    args, _ = parser.parse_known_args()
    return HostSettings(
        use_tts=not args.no_tts,
        sound_effects=not args.no_sfx,
        music=not args.no_music,
        fullscreen=args.fullscreen or os.getenv("SteamDeck", "0") == "1",
        software_renderer=args.software_renderer,
    )


def run(definition: GameDefinition, home: GameDefinition | None = None) -> None:
    """Runs a game in its own window until it quits, then exits the process.

    The player's options come from the command line:

    - ``--fullscreen``: start fullscreen. Always on for a Steam Deck.
    - ``--no-music``: no music.
    - ``--no-sfx``: no sound effects.
    - ``--no-tts``: no spoken intro; it is shown on timers instead.
    - ``--software-renderer``: draw without OpenGL.

    Args:
        definition: The game to start.
        home: An app to return to when the game quits, such as a launcher.
    """
    settings = parse_settings(definition.info.title)
    start_logging()
    if not settings.software_renderer:
        use_opengl_format()
    application = QApplication(sys.argv)
    log_system_info(use_hardware=not settings.software_renderer)
    refresh_rate = application.primaryScreen().refreshRate() or 60.0
    window = HostWindow(definition, settings, refresh_rate, home=home)
    application.aboutToQuit.connect(window.host.shutdown)
    window.show()
    sys.exit(application.exec())
