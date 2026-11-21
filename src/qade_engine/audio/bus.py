# SPDX-License-Identifier: GPL-3.0-or-later
"""Realtime sound effects, each voice on its own SDL_mixer channel."""

import logging
import math
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from sdl2 import sdlmixer as mix

from qade_engine.core import clamp

from . import device
from .synth import RATE, Sound, bake, layers

_log = logging.getLogger(__name__)


@dataclass(eq=False, slots=True)
class _Sound:
    gap: float
    priority: int
    loop: bool
    voices: list["_Voice"] = field(default_factory=list)
    last: float = -math.inf
    last_voice: "_Voice | None" = None


@dataclass(eq=False, slots=True)
class _Voice:
    chunk: object
    channel: int
    duration: float
    sound: _Sound
    start: float = 0.0
    end: float = 0.0  # 0 = idle, inf = looping until stopped


class SoundBus:
    """Plays registered sounds by name.

    ``ArcadeGame`` creates one and hands it to ``register_sounds``; other
    apps get one from ``open_bus``.

    Only a few sounds are audible at once. When full, the lowest-priority
    (then oldest) sound is cut if the new one is at least as important;
    otherwise the new one is dropped. Sound never affects the simulation.
    """

    def __init__(
        self,
        max_voices: int = 5,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Creates an empty bus.

        Args:
            max_voices: Sounds audible at once.
            clock: Returns seconds, for gaps and voice ages.

        Raises:
            OSError: There's no audio device.
        """
        if not device.available():
            raise OSError("no audio device")
        self._sounds: dict[str, _Sound] = {}
        self._voices: list[_Voice] = []
        self._max = max_voices
        self._now = clock
        self._warned: set[str] = set()
        # Its own generator: drawing from the global one would shift a game's
        # random sequence depending on whether sound effects are on.
        self._rng = random.Random()

    def register(
        self,
        name: str,
        sound: Sound,
        voices: int = 2,
        spread: float = 0.04,
        semitones: Sequence[float] | None = None,
        gap: float = 0.0,
        priority: int = 1,
    ) -> None:
        """Bakes a sound and makes it playable by name.

        Args:
            name: The name to play it by.
            sound: An ``Sfx``, or a list of layers.
            voices: Most copies of this sound playing at once.
            spread: Pitch variation, as a fraction, spread evenly across the
                voices.
            semitones: An explicit pitch per voice instead, such as
                ``[0, 2, 4, 7]``. Choose one with ``play(step=i)``.
            gap: Fewest seconds between triggers, to stop machine-gunning.
            priority: 0 ambient, 1 normal, 2 important, 3 critical. Decides
                which sound is cut when the bus is full.

        Raises:
            ValueError: The name is taken, or a looping sound has layers.
            OSError: The mixer can't load the baked sound.
        """
        if name in self._sounds:
            raise ValueError(f"sound {name!r} is already registered")
        parts = layers(sound)
        loop = any(s.loop for s, _ in parts)
        if loop and (len(parts) > 1 or parts[0][1]):
            raise ValueError("a looping sound must be a single Sfx with no delay")
        if loop:
            pitches = [1.0]
        elif semitones:
            pitches = [2 ** (st / 12) for st in semitones]
        elif voices > 1:
            pitches = [1 + spread * (2 * i / (voices - 1) - 1) for i in range(voices)]
        else:
            pitches = [1.0]
        registered = _Sound(gap, priority, loop)
        for pitch in pitches:
            pcm = bake(sound, pitch)
            chunk = device.load_chunk(pcm)
            voice = _Voice(chunk, device.take_channel(), len(pcm) / RATE, registered)
            registered.voices.append(voice)
            self._voices.append(voice)
        self._sounds[name] = registered

    def play(self, name: str, step: int | None = None, vol: float = 1.0) -> bool:
        """Triggers a sound. A looping sound plays until stopped.

        Args:
            name: The registered sound.
            step: Which pitch from ``semitones`` to play, clamped to the last.
            vol: Volume, 0 to 1.

        Returns:
            True if it started, or, for a loop, is running.
        """
        sound = self._sounds.get(name)
        if sound is None:
            if name not in self._warned:
                self._warned.add(name)
                _log.warning("play(%r): no such sound registered", name)
            return False
        now = self._now()
        if sound.loop and sound.voices[0].end > now:
            return True
        if now - sound.last < sound.gap:
            return False

        voice = self._pick_voice(sound, step, now)
        if voice.end <= now and not self._make_room(sound.priority, now):
            return False
        mix.Mix_Volume(voice.channel, round(clamp(vol, 0.0, 1.0) * mix.MIX_MAX_VOLUME))
        if mix.Mix_PlayChannel(voice.channel, voice.chunk, -1 if sound.loop else 0) < 0:
            _log.warning("play(%r): %s", name, device.error())
            voice.end = 0.0
            return False
        voice.start = now
        voice.end = math.inf if sound.loop else now + voice.duration
        sound.last, sound.last_voice = now, voice
        return True

    def stop(self, name: str) -> None:
        """Stops every voice of a sound. An unknown name is ignored.

        Args:
            name: The registered sound.
        """
        sound = self._sounds.get(name)
        if sound is None:
            return
        for voice in sound.voices:
            self._silence(voice)

    def stop_loops(self) -> None:
        """Stops every looping sound, letting one-shots ring out."""
        for voice in self._voices:
            if voice.sound.loop:
                self._silence(voice)

    def stop_all(self) -> None:
        """Stops every sound."""
        for voice in self._voices:
            self._silence(voice)

    def close(self) -> None:
        """Stops everything and releases every voice, leaving the bus empty."""
        for voice in self._voices:
            device.release_channel(voice.channel)
            mix.Mix_FreeChunk(voice.chunk)
        self._voices.clear()
        self._sounds.clear()

    def _pick_voice(self, sound: _Sound, step: int | None, now: float) -> _Voice:
        """Chooses which of a sound's voices to play.

        The voice ``step`` names; else a random idle one, never the same twice
        running; else, all busy, the oldest, to restart.
        """
        voices = sound.voices
        if step is not None:
            return voices[clamp(int(step), 0, len(voices) - 1)]
        idle = [v for v in voices if v.end <= now]
        if not idle:
            return min(voices, key=lambda v: v.start)
        return self._rng.choice([v for v in idle if v is not sound.last_voice] or idle)

    def _make_room(self, priority: int, now: float) -> bool:
        """Frees a voice for one more sound if the bus is full.

        Cuts the lowest-priority, then oldest, sound. Returns False, cutting
        nothing, if every one outranks ``priority``.
        """
        active = [v for v in self._voices if v.end > now]
        if len(active) < self._max:
            return True
        # A loop is started once, so one cut here would never come back.
        victim = min(
            [v for v in active if not v.sound.loop] or active,
            key=lambda v: (v.sound.priority, v.start),
        )
        if victim.sound.priority > priority:
            return False
        self._silence(victim)
        return True

    def _silence(self, voice: _Voice) -> None:
        mix.Mix_HaltChannel(voice.channel)
        voice.end = 0.0


def open_bus(register: Callable[[SoundBus], None]) -> SoundBus | None:
    """Creates a bus and registers sounds on it.

    Args:
        register: Registers the sounds, such as ``ArcadeGame.register_sounds``.

    Returns:
        The bus, or None if there's no audio device or a sound won't load,
        so the app plays on without sound effects.
    """
    try:
        bus = SoundBus()
    except OSError as exc:
        _log.error("sound effects off: %s", exc)
        return None
    try:
        register(bus)
    except OSError as exc:
        bus.close()
        _log.error("sound effects off: %s", exc)
        return None
    return bus
