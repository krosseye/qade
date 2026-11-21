# SPDX-License-Identifier: GPL-3.0-or-later
from qade_engine.audio import Sfx, SoundBus

SHOT = "shot"
KILL = "kill"
TEAR = "tear"
BOARD = "board"
DOOR = "door"
HURT = "hurt"
ROUND = "round"

_SHOT = [
    Sfx("noise", 20000, sweep=12000, dur=0.035, decay=4, bits=6, vol=0.32),
    Sfx("tri", 150, sweep=45, dur=0.09, decay=2.5, vol=0.3),
    (Sfx("noise", 6000, sweep=2000, dur=0.2, decay=3.5, bits=4, vol=0.13), 0.01),
]

_KILL = [
    Sfx("noise", 7000, sweep=1200, dur=0.12, decay=2.5, bits=3, vol=0.22),
    Sfx(
        "buzz",
        150,
        sweep=80,
        dur=0.3,
        decay=1.5,
        wobble=0.06,
        wobble_hz=7,
        bits=4,
        vol=0.12,
    ),
    (Sfx("tri", 110, sweep=40, dur=0.18, decay=2, vol=0.3), 0.06),
]

_TEAR = [
    Sfx(
        "saw",
        240,
        sweep=170,
        dur=0.16,
        decay=0.8,
        wobble=0.12,
        wobble_hz=30,
        bits=4,
        vol=0.14,
    ),
    (Sfx("noise", 14000, sweep=3000, dur=0.08, decay=3, bits=3, vol=0.26), 0.14),
    (Sfx("tri", 180, sweep=120, dur=0.06, decay=2, vol=0.18), 0.32),
    (Sfx("tri", 150, sweep=110, dur=0.05, decay=2, vol=0.1), 0.4),
]

_HAMMER = [
    Sfx("square", 1400, sweep=900, dur=0.03, decay=4, duty=0.25, vol=0.12),
    Sfx("tri", 220, sweep=140, dur=0.07, decay=2.5, vol=0.28),
]
_BOARD = [*_HAMMER, *((blow, 0.13) for blow in _HAMMER)]

_DOOR = [
    Sfx("square", 1600, dur=0.03, decay=3, duty=0.125, vol=0.1),
    (
        Sfx(
            "square",
            420,
            sweep=560,
            dur=0.6,
            decay=0.6,
            duty=0.125,
            wobble=0.25,
            wobble_hz=18,
            bits=4,
            vol=0.14,
        ),
        0.05,
    ),
    (Sfx("tri", 90, sweep=50, dur=0.15, decay=2, vol=0.3), 0.62),
]

_HURT = [
    Sfx("noise", 16000, sweep=4000, dur=0.12, decay=2, bits=4, vol=0.22),
    Sfx("tri", 90, sweep=40, dur=0.2, decay=1.5, vol=0.34),
    (Sfx("buzz", 200, sweep=130, dur=0.22, decay=1.2, bits=4, vol=0.16), 0.04),
]


def _moan(freq: float, delay: float, wobble_hz: float) -> tuple[Sfx, float]:
    """One voice of the horde."""
    moan = Sfx(
        "buzz",
        freq,
        sweep=freq * 0.75,
        dur=1.3,
        decay=1.0,
        wobble=0.07,
        wobble_hz=wobble_hz,
        bits=4,
        vol=0.18,
    )
    return moan, delay


_ROUND = [_moan(110, 0.0, 4), _moan(147, 0.25, 3), _moan(92, 0.5, 5)]


def register(bus: SoundBus) -> None:
    bus.register(SHOT, _SHOT, voices=3, spread=0.06)
    bus.register(KILL, _KILL, voices=2)
    bus.register(TEAR, _TEAR, priority=2)
    bus.register(BOARD, _BOARD)
    bus.register(DOOR, _DOOR, voices=1, priority=2)
    bus.register(HURT, _HURT, priority=3)
    bus.register(ROUND, _ROUND, voices=1, priority=2)
