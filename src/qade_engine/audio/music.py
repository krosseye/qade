# SPDX-License-Identifier: GPL-3.0-or-later
"""Background music: one track looping or played once."""

from pathlib import Path

from sdl2 import sdlmixer as mix

from . import device

_on: "MusicTrack | None" = None


class MusicTrack:
    """Plays a WAV file. ``start`` and ``stop`` are safe to call repeatedly.

    A one-shot plays once: ``start`` won't replay it once it has finished.
    Stopped part-way, it carries on from there.
    """

    def __init__(self, path: str | Path, volume: float = 0.25, loop: bool = True):
        """Loads the track, silent until ``start``.

        Args:
            path: The WAV file.
            volume: Volume, 0 to 1.
            loop: Repeat forever, or play once.

        Raises:
            OSError: There's no audio device, or the file won't load.
        """
        if not device.available():
            raise OSError("no audio device")
        self._music = mix.Mix_LoadMUS(str(path).encode())
        if not self._music:
            raise OSError(f"can't load {path}: {device.error()}")
        self._volume = round(volume * mix.MIX_MAX_VOLUME)
        self._loops = -1 if loop else 1
        self._active = False
        self._paused = False
        self._finished = False

    @property
    def finished(self) -> bool:
        """A one-shot that has played through."""
        if self._active and not self._current():
            self._active = False
            self._finished = _on is self
        return self._finished

    def start(self) -> None:
        """Starts or carries on playing, unless already playing or a one-shot
        that has ended."""
        global _on
        if self._active or self.finished:
            return
        self._active = True
        mix.Mix_VolumeMusic(self._volume)
        if self._paused and self._current():
            mix.Mix_ResumeMusic()
        else:
            _on = self
            mix.Mix_PlayMusic(self._music, self._loops)
        self._paused = False

    def stop(self) -> None:
        """Pauses, to carry on from here at the next ``start``."""
        if not self._active:
            return
        self._active = False
        self._paused = True
        mix.Mix_PauseMusic()

    def close(self) -> None:
        """Stops for good and frees the track. Safe to call more than once."""
        global _on
        if _on is self:
            _on = None
        if self._music:
            mix.Mix_FreeMusic(self._music)
            self._music = None
        self._active = self._paused = False

    def _current(self) -> bool:
        """Whether the mixer is on this track, playing or paused."""
        return _on is self and bool(mix.Mix_PlayingMusic())
