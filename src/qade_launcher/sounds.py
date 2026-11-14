# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher sound effects, synthesised by the engine's sound bus."""

from qade_engine.audio import Sfx, SoundBus, presets

SELECT = "select"
END = "end"
COIN = "coin"
POWER_UP = "power_up"

UNIT_SEMITONES = (0, 2, 4, 7, 9, 12, 14, 16)


def register(bus: SoundBus) -> None:
    bus.register(
        SELECT,
        Sfx("square", 660, dur=0.07, decay=1.5, duty=0.125, vol=0.11),
        semitones=UNIT_SEMITONES,
    )
    bus.register(END, Sfx("tri", 110, sweep=70, dur=0.1, decay=2, vol=0.22), gap=0.1)
    bus.register(
        COIN, presets.jingle("B5 E6", speed=1.6, vol=0.16), voices=1, priority=2
    )
    bus.register(
        POWER_UP,
        [
            (Sfx("saw", 90, sweep=520, dur=0.55, decay=0.6, bits=5, vol=0.1), 0.12),
            (Sfx("noise", 600, sweep=5200, dur=0.5, decay=0.8, bits=4, vol=0.06), 0.15),
        ],
        voices=1,
        priority=2,
    )
