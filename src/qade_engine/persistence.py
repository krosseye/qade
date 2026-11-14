# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved data: each game's high score, under ``~/.qade``."""

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)

SAVE_ROOT = Path.home() / ".qade"


class HighScoreStore:
    """Keeps one integer high score in a JSON file.

    Attributes:
        path: The file.
    """

    def __init__(self, path: str | Path):
        """Creates a store.

        Args:
            path: The file to keep the score in.
        """
        self.path = Path(path)

    @classmethod
    def for_game(cls, game_id: str) -> "HighScoreStore":
        """A store at the standard location, ``~/.qade/<game_id>/highscore.json``.

        Args:
            game_id: The game's ``GameInfo.id``.

        Returns:
            The store.
        """
        return cls(SAVE_ROOT / game_id / "highscore.json")

    def load(self) -> int:
        """Reads the high score.

        Returns:
            The score, or 0 if the file is missing, unreadable or corrupt.
        """
        try:
            data = json.loads(self.path.read_text())
            return max(0, int(data["high_score"]))
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            return 0

    def save(self, score: int) -> None:
        """Saves a score, unless the file already holds a better one.

        Args:
            score: The score to save.
        """
        score = max(int(score), self.load())
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps({"high_score": int(score)}))
            temp.replace(self.path)
        except OSError as exc:
            _log.warning("could not save high score: %s", exc)
