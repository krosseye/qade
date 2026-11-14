# SPDX-License-Identifier: GPL-3.0-or-later
"""Retro sound synthesis: a sound described by a few numbers, rendered to samples."""

from dataclasses import dataclass
from functools import cache

import numpy as np

RATE = 22050
WAVES = ("square", "tri", "saw", "noise", "buzz")
_FADE_IN, _FADE_OUT = int(RATE * 0.002), int(RATE * 0.005)


@dataclass(frozen=True)
class Sfx:
    """One synthesised sound.

    Attributes:
        wave: One of ``square``, ``tri``, ``saw``, ``noise`` or ``buzz``.
        freq: Pitch in Hz. For noise, the clock rate: high hisses, low rumbles.
        sweep: End frequency, slid to exponentially from ``freq``. None holds
            the pitch.
        dur: Length in seconds, from 0.02 to 10.
        decay: Fade-out curve: 0 flat, 1 linear, 3 a sharp pluck.
        duty: Square only. Pulse width, from 0.5 hollow to 0.125 thin.
        wobble: Vibrato depth as a fraction of ``freq``: 0.05 subtle, 0.4 a siren.
        bits: Bit-crush depth: 3 crunchy, 8 clean.
        vol: The sound's own peak level, from 0 to 1.
        duty_end: Square only. Pulse width slides from ``duty`` to this.
        steps: An arpeggio: one frequency per equal slice of ``dur``.
        wobble_hz: Vibrato speed.
        loop: A seamless loop. Only for a steady sound: ``decay=0`` and no
            sweep, steps or ``duty_end``.

    Raises:
        ValueError: A value is out of range, or the combination is invalid.
    """

    wave: str = "square"
    freq: float = 440.0
    sweep: float | None = None
    dur: float = 0.2
    decay: float = 2.0
    duty: float = 0.5
    wobble: float = 0.0
    bits: int = 5
    vol: float = 0.4
    duty_end: float | None = None
    steps: tuple[float, ...] | None = None
    wobble_hz: float = 12.0
    loop: bool = False

    def __post_init__(self):
        def need(ok, msg):
            if not ok:
                raise ValueError(f"Sfx: {msg}")

        need(self.wave in WAVES, f"wave {self.wave!r} is not one of {WAVES}")
        if self.steps is None:
            need(self.freq > 0, "freq must be > 0")
        else:
            need(
                len(self.steps) > 0 and min(self.steps) > 0,
                "steps must be a non-empty list of Hz > 0",
            )
            need(self.sweep is None, "sweep can't be combined with steps")
        need(self.sweep is None or self.sweep > 0, "sweep must be > 0")
        need(0.02 <= self.dur <= 10, "dur must be between 0.02 and 10 seconds")
        need(self.decay >= 0, "decay must be >= 0")
        need(0 < self.duty < 1, "duty must be between 0 and 1")
        need(
            self.duty_end is None or (self.wave == "square" and 0 < self.duty_end < 1),
            "duty_end needs wave='square' and a value between 0 and 1",
        )
        need(0 <= self.wobble < 1, "wobble must be in [0, 1)")
        need(self.wobble_hz > 0, "wobble_hz must be > 0")
        need(1 <= self.bits <= 16, "bits must be 1-16")
        need(0 < self.vol <= 1, "vol must be in (0, 1]")
        need(
            not self.loop
            or (
                self.decay == 0
                and self.sweep is None
                and self.steps is None
                and self.duty_end is None
            ),
            "a looping sound must be steady: decay=0 and no sweep, steps or duty_end",
        )


Sound = Sfx | list  # an Sfx, or a list of Sfx / (Sfx, delay_seconds) layers

_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(note: str) -> float:
    """Converts a note name to its frequency.

    Args:
        note: A name such as ``"A4"``, ``"C#5"`` or ``"Bb3"``.

    Returns:
        The frequency in Hz. ``"A4"`` is 440.

    Raises:
        ValueError: The name isn't a note.
    """
    try:
        semi, rest = _SEMI[note[0].upper()], note[1:]
        if rest[0] in "#b":
            semi += 1 if rest[0] == "#" else -1
            rest = rest[1:]
        return 440.0 * 2 ** ((12 * (int(rest) + 1) + semi - 69) / 12)
    except (KeyError, IndexError, ValueError):
        raise ValueError(
            f"bad note name {note!r} (expected e.g. 'C5', 'F#3', 'Bb4')"
        ) from None


@cache
def _lfsr(tap: int, length: int) -> np.ndarray:
    """15-bit shift-register noise as used by NES/POKEY-era chips, as +-1 samples.

    tap=1, length=32767: long, hissy.  tap=6, length=93: short, buzzy and *pitched*.
    """
    r, out = 1, []
    for _ in range(length):
        out.append(r & 1)
        r = (r >> 1) | (((r ^ (r >> tap)) & 1) << 14)
    return np.array(out, dtype=np.float64) * 2 - 1


def render(s: Sfx, pitch: float = 1.0) -> np.ndarray:
    """Renders one sound to samples.

    Args:
        s: The sound.
        pitch: Frequency multiplier.

    Returns:
        Mono 16-bit samples at ``RATE``.
    """
    n = round(RATE * s.dur)
    f0 = s.freq * pitch
    if s.loop and s.wave != "noise":
        # Whole number of cycles, so the wrap point lands exactly on the waveform start.
        cycles = max(1, round(f0 * s.dur))
        n = round(cycles * RATE / f0)
        f0 = cycles * RATE / n
    t = np.arange(n) / n

    gate: np.ndarray | float
    if s.steps:
        k = len(s.steps)
        pos = t * k
        f = np.asarray(s.steps)[np.minimum(pos.astype(int), k - 1)] * pitch
        gate = np.clip((1 - pos % 1.0) / 0.15, 0, 1)  # short gap between notes
    else:
        f = np.full(n, f0)
        if s.sweep:
            f *= (s.sweep / s.freq) ** t
        gate = 1.0
    if s.wobble:
        cw = s.wobble_hz * n / RATE
        if s.loop:
            cw = max(1, round(cw))  # vibrato must also loop cleanly
        f = f * (1 + s.wobble * np.sin(2 * np.pi * cw * t))

    ph = np.cumsum(f) / RATE
    if s.wave == "noise":
        y = _lfsr(1, 32767)[ph.astype(np.int64) % 32767]
    elif s.wave == "buzz":
        y = _lfsr(6, 93)[(ph % 1.0 * 93).astype(np.int64)]
    else:
        frac = ph % 1.0
        if s.wave == "square":
            duty = (
                np.linspace(s.duty, s.duty_end, n) if s.duty_end is not None else s.duty
            )
            y = np.where(frac < duty, 1.0, -1.0)
        elif s.wave == "tri":
            y = 4 * np.abs(frac - 0.5) - 1
        else:
            y = 2 * frac - 1

    env = (1 - t) ** s.decay * gate
    if not s.loop:
        env[:_FADE_IN] *= np.linspace(0, 1, _FADE_IN)
        env[-_FADE_OUT:] *= np.linspace(1, 0, _FADE_OUT)
    q = 2 ** (s.bits - 1)
    # Crushed after the envelope, so the decay itself steps down audibly.
    y = np.round(y * env * q) / q
    return np.rint(y * s.vol * 32767).astype(np.int16)


def layers(sound: Sound) -> list[tuple[Sfx, float]]:
    """Normalises a sound to a list of layers.

    Args:
        sound: An ``Sfx``, or a list of ``Sfx`` and ``(Sfx, delay_seconds)``.

    Returns:
        The layers, as ``(Sfx, delay_seconds)`` pairs.

    Raises:
        ValueError: The sound is empty or has something other than ``Sfx``
            layers with non-negative delays.
    """
    if isinstance(sound, Sfx):
        return [(sound, 0.0)]
    out = [(x, 0.0) if isinstance(x, Sfx) else (x[0], float(x[1])) for x in sound]
    if not out or not all(isinstance(s, Sfx) and d >= 0 for s, d in out):
        raise ValueError("a sound is an Sfx or a list of Sfx / (Sfx, delay_seconds)")
    return out


def bake(sound: Sound, pitch: float = 1.0) -> np.ndarray:
    """Renders a sound, summing its layers.

    The sum is scaled so it never peaks above its loudest layer's ``vol``.

    Args:
        sound: An ``Sfx``, or a list of layers.
        pitch: Frequency multiplier.

    Returns:
        Mono 16-bit samples at ``RATE``.
    """
    parts_in = layers(sound)
    if len(parts_in) == 1 and parts_in[0][1] == 0:
        return render(parts_in[0][0], pitch)
    parts = [(round(d * RATE), render(s, pitch)) for s, d in parts_in]
    buf = np.zeros(max(o + len(p) for o, p in parts))
    for o, p in parts:
        buf[o : o + len(p)] += p
    peak = np.abs(buf).max()
    if peak:
        buf *= max(s.vol for s, _ in parts_in) * 32767 / peak
    return np.rint(buf).astype(np.int16)
