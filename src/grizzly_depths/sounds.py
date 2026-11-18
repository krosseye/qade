# SPDX-License-Identifier: GPL-3.0-or-later
"""Grizzly Depths sound effects, synthesised by the engine's sound bus."""

from qade_engine.audio import Sfx, SoundBus, presets
from qade_engine.core import clamp

from . import config

STEP = "step"
BUMP = "bump"
TURN = "turn"
HEART = "heart"
BEAR_STEP = "bear_step"
ROAR = "roar"
EXIT = "exit"
RESONATE = "resonate"
HUM = "hum"
TICK = "tick"
MAULED = "mauled"

# The charge's ticks climb a scale, an octave and a half, as it fills.
TICK_SEMITONES = (0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19)

_ROAR = [
    Sfx(
        "buzz",
        120,
        sweep=55,
        dur=0.9,
        decay=1.2,
        wobble=0.08,
        wobble_hz=9,
        bits=4,
        vol=0.3,
    ),
    (Sfx("noise", 1400, sweep=260, dur=0.8, decay=1.6, bits=4, vol=0.22), 0.04),
]


def register(bus: SoundBus) -> None:
    bus.register(
        STEP, Sfx("noise", 1800, sweep=700, dur=0.06, decay=3, bits=4, vol=0.1)
    )
    bus.register(BUMP, Sfx("tri", 95, sweep=50, dur=0.09, decay=2, vol=0.25), gap=0.1)
    bus.register(
        TURN, Sfx("noise", 4200, sweep=1600, dur=0.07, decay=2, bits=5, vol=0.05)
    )
    bus.register(HEART, presets.thump(), semitones=[0, -2], priority=2)

    bus.register(
        BEAR_STEP,
        [
            Sfx("noise", 320, sweep=110, dur=0.13, decay=2, bits=3, vol=0.3),
            Sfx("tri", 60, sweep=40, dur=0.12, decay=1.5, vol=0.3),
        ],
        priority=2,
    )
    bus.register(ROAR, _ROAR, voices=1, priority=2)
    bus.register(EXIT, presets.jingle("C5 E5 G5 C6"), voices=1, priority=2)

    bell = [
        Sfx("square", 1975, dur=0.7, decay=2.5, duty=0.25, bits=6, vol=0.16),
        Sfx("tri", 2960, dur=0.5, decay=3, vol=0.1),
    ]
    bus.register(
        RESONATE,
        [
            *bell,
            *((Sfx("square", 1975, dur=0.5, decay=3, duty=0.25, vol=0.06), 0.28),),
            *((Sfx("square", 1975, dur=0.4, decay=3, duty=0.25, vol=0.03), 0.56),),
        ],
        voices=1,
        priority=2,
    )
    bus.register(
        HUM,
        Sfx(
            "tri", 880, dur=1.0, decay=0, wobble=0.02, wobble_hz=6, vol=0.07, loop=True
        ),
    )
    bus.register(
        TICK,
        Sfx("square", 1320, dur=0.05, decay=2, duty=0.125, bits=6, vol=0.08),
        semitones=TICK_SEMITONES,
    )
    bus.register(MAULED, [*_ROAR, *presets.explosion(1.2)], voices=1, priority=3)


def bear_volume(path_distance: int) -> float:
    """Louder the closer it is by path (sound follows the tunnels, not walls)."""
    reach = config.APPROACH_DISTANCE + 3
    return clamp(1.0 - path_distance / reach, 0.0, 1.0)


def heartbeat_interval(path_distance: int) -> float | None:
    """Seconds between beats, or None when the bear is too far to feel."""
    if path_distance > config.APPROACH_DISTANCE:
        return None
    closeness = 1.0 - path_distance / config.APPROACH_DISTANCE
    return 0.9 - 0.6 * closeness


def tick_interval(charge: float) -> float:
    """Seconds between the crystal's ticks, for ``charge`` from 0 to 1:
    quicker as it fills, like a clock running out."""
    return 0.45 - 0.35 * charge
