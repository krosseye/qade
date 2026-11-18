# SPDX-License-Identifier: GPL-3.0-or-later
"""Background music: one track looping or played once."""

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect


class MusicTrack(QObject):
    """Plays a WAV file. ``start`` and ``stop`` are safe to call repeatedly.

    A one-shot plays once: ``start`` won't replay it once it has finished.
    Stopped part-way, it starts again from the top.
    """

    def __init__(self, path: str | Path, volume: float = 0.25, loop: bool = True):
        """Loads the track, silent until ``start``.

        Args:
            path: The WAV file.
            volume: Volume, 0 to 1.
            loop: Repeat forever, or play once.
        """
        super().__init__()
        self._active = False
        self._finished = False
        self._effect = QSoundEffect(self)
        self._effect.setSource(QUrl.fromLocalFile(str(path)))
        self._effect.setVolume(volume)
        self._effect.setLoopCount(QSoundEffect.Loop.Infinite.value if loop else 1)
        self._effect.playingChanged.connect(self._playing_changed)

    @property
    def finished(self) -> bool:
        """A one-shot that has played through."""
        return self._finished

    def start(self):
        """Starts playing, unless already playing or a one-shot that has ended."""
        if self._active or self._finished:
            return
        self._active = True
        self._effect.play()

    def stop(self):
        """Stops playing."""
        if not self._active:
            return
        self._active = False
        self._effect.stop()

    def _playing_changed(self):
        if self._active and not self._effect.isPlaying():
            self._active, self._finished = False, True
