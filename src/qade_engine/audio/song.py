# SPDX-License-Identifier: GPL-3.0-or-later
"""Music for the sound chip.

A song is a few parts played together. Each part is one channel: an
instrument (an ``Sfx`` whose pitch and length each note fills in) or a drum
kit, and a pattern of steps written as text::

    "C4 - E4 - G4 - - - | A3+C4+E4 - - - . . . ."

* A note name starts a note: ``C4``, ``F#3``, ``Bb2``.
* ``-`` holds the note before it for another step.
* ``.`` is a rest.
* Notes joined with ``+`` are an arpeggio: the chip cycles through them fast.
* In a kit part, a token is the name of a drum: ``k``, ``s``, ``h``.
* ``|`` is a bar line, for reading only.
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .cache import write_wav
from .synth import RATE, Sfx, hz, render

MAX_PARTS = 4
"""Channels the music chip has."""

HEADROOM = 0.9
"""Peak level of a baked song, as a fraction of full scale."""

_CUT_FADE = int(RATE * 0.004)
_HOLD, _REST, _BAR = "-", ".", "|"

Kit = Mapping[str, Sfx]


@dataclass(frozen=True)
class Part:
    """One channel of a song.

    Attributes:
        pattern: The steps, as text. See the module docstring.
        instrument: An ``Sfx`` for pitched notes, whose ``freq`` and ``dur``
            each note replaces, or a kit mapping drum names to sounds.
        gate: The share of a note's held steps that it sounds for: 1 legato,
            0.5 short and punchy.
        arp_speed: Notes per second in an arpeggio.
    """

    pattern: str
    instrument: Sfx | Kit
    gate: float = 1.0
    arp_speed: float = 30.0

    def __post_init__(self) -> None:
        if not 0 < self.gate <= 1:
            raise ValueError("Part: gate must be in (0, 1]")
        if self.arp_speed <= 0:
            raise ValueError("Part: arp_speed must be > 0")
        if isinstance(self.instrument, Sfx) and self.instrument.loop:
            raise ValueError("Part: an instrument can't be a looping Sfx")

    @property
    def steps(self) -> list[str]:
        """The pattern's tokens, one per step, bar lines removed."""
        return [t for t in self.pattern.split() if t != _BAR]


@dataclass(frozen=True)
class Song:
    """A short piece of music for the sound chip.

    Attributes:
        name: For messages and the cache.
        bpm: Beats per minute.
        parts: The channels, at most ``MAX_PARTS``.
        steps_per_beat: Pattern steps in a beat. 4 makes each step a 16th note.
        loop: True for background music that repeats seamlessly. False for a
            one-shot, such as a jingle, which lets its last notes ring out.
    """

    name: str
    bpm: float
    parts: tuple[Part, ...]
    steps_per_beat: int = 4
    loop: bool = True

    def __post_init__(self) -> None:
        if not 20 <= self.bpm <= 400:
            raise ValueError(f"{self.name}: bpm must be between 20 and 400")
        if self.steps_per_beat < 1:
            raise ValueError(f"{self.name}: steps_per_beat must be >= 1")
        if not 1 <= len(self.parts) <= MAX_PARTS:
            raise ValueError(f"{self.name}: a song has 1 to {MAX_PARTS} parts")
        lengths = [len(p.steps) for p in self.parts]
        if min(lengths) == 0:
            raise ValueError(f"{self.name}: every part needs at least one step")
        longest = max(lengths)
        for index, length in enumerate(lengths):
            if longest % length:
                raise ValueError(
                    f"{self.name}: part {index} has {length} steps, which doesn't "
                    f"divide the song's {longest}"
                )
        for index, part in enumerate(self.parts):
            _notes(self.name, index, part)

    @property
    def step_samples(self) -> int:
        """Samples in one step. Whole, so every loop is exactly the same length."""
        return round(RATE * 60 / self.bpm / self.steps_per_beat)

    @property
    def length(self) -> int:
        """Steps in the song."""
        return max(len(p.steps) for p in self.parts)

    @property
    def seconds(self) -> float:
        """The song's length in seconds, not counting a one-shot's last tails."""
        return self.length * self.step_samples / RATE

    @property
    def key(self) -> str:
        """A hash of everything that decides the sound, for the cache."""
        return hashlib.sha1(repr((self, RATE, HEADROOM)).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class _Note:
    start: int  # step
    held: int  # steps
    freqs: tuple[float, ...] | None  # one, or an arpeggio
    drum: str | None


def _notes(song: str, index: int, part: Part) -> list[_Note]:
    """Parses a part's pattern into notes."""
    kit = not isinstance(part.instrument, Sfx)
    notes: list[_Note] = []
    for step, token in enumerate(part.steps):
        where = f"{song}: part {index}, step {step} ({token!r})"
        if token == _REST:
            continue
        if token == _HOLD:
            if not notes or notes[-1].start + notes[-1].held != step:
                raise ValueError(f"{where}: a hold must follow a note or a hold")
            notes[-1] = replace(notes[-1], held=notes[-1].held + 1)
            continue
        if kit:
            assert not isinstance(part.instrument, Sfx)
            if token not in part.instrument:
                drums = ", ".join(sorted(part.instrument))
                raise ValueError(f"{where}: not a drum in the kit ({drums})")
            notes.append(_Note(step, 1, None, token))
            continue
        try:
            freqs = tuple(hz(name) for name in token.split("+"))
        except ValueError as exc:
            raise ValueError(f"{where}: {exc}") from None
        notes.append(_Note(step, 1, freqs, None))
    return notes


def _render_note(part: Part, note: _Note, step_seconds: float) -> np.ndarray:
    if note.drum is not None:
        assert not isinstance(part.instrument, Sfx)
        return render(part.instrument[note.drum])
    assert isinstance(part.instrument, Sfx) and note.freqs is not None
    dur = max(0.02, min(10.0, note.held * step_seconds * part.gate))
    if len(note.freqs) == 1:
        return render(replace(part.instrument, freq=note.freqs[0], dur=dur))
    cycles = max(1, round(dur * part.arp_speed / len(note.freqs)))
    return render(
        replace(
            part.instrument,
            freq=note.freqs[0],
            sweep=None,
            steps=note.freqs * cycles,
            dur=dur,
        )
    )


def bake_song(song: Song) -> np.ndarray:
    """Renders a song.

    A looping song comes out exactly ``length * step_samples`` long, with the
    tails of its last notes wrapped round onto its start, so it loops with no
    seam. A one-shot runs on until its last note has rung out.

    Args:
        song: The song.

    Returns:
        Mono 16-bit samples at ``RATE``, peaking at ``HEADROOM``.
    """
    mix = _mix(song)
    peak = np.abs(mix).max()
    if peak:
        mix *= HEADROOM * 32767 / peak
    return np.rint(mix).astype(np.int16)


def _mix(song: Song) -> np.ndarray:
    """Every part summed at the instruments' own levels, before normalising."""
    step = song.step_samples
    total = song.length * step
    placed: list[tuple[int, np.ndarray]] = []

    for index, part in enumerate(song.parts):
        notes = _notes(song.name, index, part)
        repeats = song.length // len(part.steps)
        played = [
            (note.start + r * len(part.steps), note)
            for r in range(repeats)
            for note in notes
        ]
        for i, (onset, note) in enumerate(played):
            samples = _render_note(part, note, step / RATE).astype(np.float64)
            if i + 1 < len(played):
                room = (played[i + 1][0] - onset) * step
            elif song.loop:
                room = (played[0][0] + song.length - onset) * step
            else:
                room = len(samples)
            if len(samples) > room:
                samples = samples[:room].copy()
                fade = min(_CUT_FADE, room)
                samples[room - fade :] *= np.linspace(1.0, 0.0, fade)
            placed.append((onset * step, samples))

    if song.loop:
        mix = np.zeros(total)
        for start, samples in placed:
            np.add.at(mix, (start + np.arange(len(samples))) % total, samples)
    else:
        mix = np.zeros(max([total, *(s + len(x) for s, x in placed)]))
        for start, samples in placed:
            mix[start : start + len(samples)] += samples
    return mix


def song_path(song: Song, cache_dir: Path) -> Path:
    """Bakes a song into the cache, unless it is there already.

    Args:
        song: The song.
        cache_dir: Where baked sound is kept.

    Returns:
        The WAV file.

    Raises:
        OSError: The file can't be written.
    """
    path = cache_dir / f"song-{song.key}.wav"
    if not path.exists():
        write_wav(bake_song(song), path)
    return path
