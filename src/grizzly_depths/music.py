# SPDX-License-Identifier: GPL-3.0-or-later

from qade_engine.audio import Part, Sfx, Song

AIR = Sfx("tri", decay=0.15, bits=6, vol=0.32)
ECHO = Sfx("tri", decay=1.0, wobble=0.015, wobble_hz=4.0, bits=5, vol=0.28)
DRONE = Sfx("tri", decay=0.1, wobble=0.006, wobble_hz=0.3, bits=6, vol=0.3)
DRIPS = {
    "d": Sfx("tri", 2637, sweep=3500, dur=0.04, decay=2.5, bits=6, vol=0.12),
    "e": Sfx("tri", 2349, sweep=3100, dur=0.04, decay=2.5, bits=6, vol=0.08),
}


def bar(token: str, steps: int = 16) -> str:
    """One note held for a whole bar, or a bar's rest for ``"."``."""
    fill = "." if token == "." else "-"
    return " ".join([token, *[fill] * (steps - 1)])


def bars(*tokens: str, steps: int = 16) -> str:
    """Whole bars of ``tokens``, one per bar."""
    return " | ".join(bar(t, steps) for t in tokens)


SONG = Song(
    name="grizzly_depths",
    bpm=60,
    parts=(
        Part(
            ". . . . . . . . E5 - - - - - - - |"
            " . . . . . . . . . . . . F5 - - - |"
            " D5 - - - - - - - . . . . . . . . |"
            " . . . . G4 - - - - - - - E5 - - - |"
            " - - - - . . . . . . . . . . . . |"
            " . . . . . . . . C#5 - - - - - - -",
            ECHO,
        ),
        Part(
            bars(
                "D3+A3+E4", "D3+A3+F4", "Bb2+F3+D4", "C3+G3+E4", "D3+A3+E4", "A2+E3+C#4"
            ),
            AIR,
            arp_speed=4.0,
        ),
        Part(bars("D3", "D3", "Bb2", "C3", "D3", "A2"), DRONE),
        Part(
            ". . . . . . d . . . . . . . . . |"
            " . . . . . . . . . . e . . . . . |"
            " . . . . . . . . . . . . . d . . |"
            " . . e . . . . . . . . . . . . . |"
            " . . . . . . . . d . . . . . e . |"
            " . . . . . . . . . . . . . . . .",
            DRIPS,
        ),
    ),
)
