# SPDX-License-Identifier: GPL-3.0-or-later
"""Ready-made sounds that need no tuning."""

from qade_engine.core import clamp

from .synth import Sfx, hz


def laser(pitch=1.0) -> Sfx:
    """A player's shot."""
    return Sfx(
        "square", 900 * pitch, sweep=180 * pitch, dur=0.14, decay=2, duty=0.25, vol=0.21
    )


def zap(pitch=1.0) -> Sfx:
    """An enemy shot or electric hit."""
    return Sfx(
        "buzz", 400 * pitch, sweep=60 * pitch, dur=0.22, decay=1.5, bits=4, vol=0.21
    )


def blip(pitch=1.0) -> Sfx:
    """A menu or UI beep."""
    return Sfx("square", 880 * pitch, dur=0.06, decay=0.5, vol=0.18)


def pickup(pitch=1.0) -> Sfx:
    """A rising chirp for a bonus or coin."""
    return Sfx(
        "square",
        400 * pitch,
        sweep=1400 * pitch,
        dur=0.18,
        decay=1,
        duty=0.125,
        vol=0.20,
    )


def thump(pitch=1.0) -> Sfx:
    """A low heartbeat.

    Register it with ``semitones=[0, -2]`` and alternate ``play(step=0)`` and
    ``play(step=1)`` for the classic pulse.
    """
    return Sfx("tri", 55 * pitch, dur=0.1, decay=1, vol=0.35)


def power_down(pitch=1.0) -> Sfx:
    """A falling saw, for a ship lost or a power failure."""
    return Sfx(
        "saw", 500 * pitch, sweep=40 * pitch, dur=0.8, decay=1.2, bits=4, vol=0.21
    )


def jingle(notes: str, speed=1.0, wave="square", vol=0.21) -> Sfx:
    """A short melody as one sound, so its timing is sample-accurate.

    Args:
        notes: Note names separated by spaces, such as ``"C5 E5 G5 C6"``.
        speed: Tempo multiplier.
        wave: The waveform.
        vol: Peak level, from 0 to 1.

    Returns:
        The melody.
    """
    freqs = tuple(hz(n) for n in notes.split())
    return Sfx(
        wave, steps=freqs, dur=len(freqs) * 0.09 / speed, decay=0.5, duty=0.25, vol=vol
    )


def explosion(size=1.0) -> list:
    """A crack, a noise boom and a buzzy rumble, layered.

    Args:
        size: 0 a pop, 1 big, 1.5 huge.

    Returns:
        The layers, for ``SoundBus.register``.
    """
    size = clamp(size, 0.0, 1.5)
    return [
        (Sfx("noise", 9000, sweep=2500, dur=0.10, decay=3, bits=3, vol=0.21), 0.0),
        (
            Sfx(
                "noise",
                5500,
                sweep=250,
                dur=0.25 + 0.55 * size,
                decay=2.2,
                bits=4,
                vol=0.32,
            ),
            0.0,
        ),
        (
            Sfx(
                "buzz",
                70,
                sweep=32,
                dur=0.30 + 0.60 * size,
                decay=1.6,
                bits=4,
                vol=0.25,
            ),
            0.02,
        ),
    ]
