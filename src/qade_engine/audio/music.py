# SPDX-License-Identifier: GPL-3.0-or-later
"""Background music: one looping track."""

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect


class MusicLoop(QObject):
    """Loops a WAV file. ``start`` and ``stop`` are safe to call repeatedly."""

    def __init__(self, path: str | Path, volume: float = 0.25):
        """Loads the track, silent until ``start``.

        Args:
            path: The WAV file.
            volume: Volume, 0 to 1.
        """
        super().__init__()
        self._active = False
        self._effect = QSoundEffect(self)
        self._effect.setSource(QUrl.fromLocalFile(str(path)))
        self._effect.setVolume(volume)
        self._effect.setLoopCount(QSoundEffect.Loop.Infinite.value)

    def start(self):
        """Starts playing, unless already playing."""
        if self._active:
            return
        self._active = True
        self._effect.play()

    def stop(self):
        """Stops playing."""
        if not self._active:
            return
        self._active = False
        self._effect.stop()
