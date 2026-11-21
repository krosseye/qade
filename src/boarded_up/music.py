# SPDX-License-Identifier: GPL-3.0-or-later
from qade_engine.audio import Part, Sfx, Song

PULSE_BASS = Sfx("tri", decay=0.6, bits=8, vol=0.7)
FIGURE = Sfx("square", duty=0.5, decay=1.6, bits=5, vol=0.3)
SYNTH = Sfx("tri", decay=0.25, wobble=0.005, wobble_hz=5.0, bits=6, vol=0.32)
RIFF = Sfx(
    "square", duty=0.25, decay=0.6, wobble=0.008, wobble_hz=6.0, bits=5, vol=0.42
)
CLUSTER = Sfx("square", duty=0.25, decay=0.8, bits=4, vol=0.2)
DEEP = Sfx("saw", decay=1.0, bits=5, vol=0.5)

DRUMS = {
    "k": Sfx("tri", 90, sweep=35, dur=0.18, decay=2.0, bits=8, vol=0.6),
    "s": Sfx("noise", 2600, sweep=1400, dur=0.08, decay=3.2, bits=4, vol=0.15),
    "h": Sfx("noise", 9000, dur=0.025, decay=3.0, bits=4, vol=0.08),
}
BOOM = {"b": Sfx("tri", 90, sweep=32, dur=0.9, decay=1.6, bits=8, vol=0.9)}

_FIGURE_NOTES = {
    "F#": ("F#4", "F#3", "C#5", "A4"),
    "D": ("D4", "D3", "A4", "F#4"),
    "E": ("E4", "E3", "B4", "G#4"),
    "C#": ("C#4", "C#3", "G#4", "E#4"),
}
_ROOTS = (
    *("F#", "F#", "D", "D", "E", "E", "C#", "C#"),
    *("D", "E", "F#", "F#", "D", "E", "C#", "C#"),
)


def _figure(top: str, bottom: str, fifth: str, third: str) -> str:
    a, b, c, d = top, bottom, fifth, third
    return f"{a} {b} {a} {b} {c} {b} {a} {b} {a} {b} {a} {b} {c} {b} {d} {b}"


_DRIVE = "k . h . s . h . k . h . s . h k"
_HALF_TIME = "k . h . h . h . s . h . h . h ."

SONG = Song(
    name="boarded_up",
    bpm=112,
    parts=(
        Part(
            " | ".join(" ".join(f"{root}2 ." for _ in range(8)) for root in _ROOTS),
            PULSE_BASS,
            gate=0.7,
        ),
        Part(
            " | ".join(_figure(*_FIGURE_NOTES[root]) for root in _ROOTS),
            FIGURE,
            gate=0.5,
        ),
        Part(" | ".join([_DRIVE] * 8 + [_HALF_TIME] * 8), DRUMS),
        Part(
            # A
            "C#5 - - - - - - - - - - - - - - - |"
            " A4 - - - - - - - B4 - - - - - - - |"
            " A4 - - - - - - - - - - - F#4 - - - |"
            " D5 - - - - - - - C#5 - - - - - - - |"
            " B4 - - - - - - - - - - - G#4 - - - |"
            " E5 - - - - - - - D5 - - - - - - - |"
            " C#5 - - - - - - - - - - - E#5 - - - |"
            " G#5 - - - - - - - - - - - . . . . |"
            # B
            " F#5 - - - - - - - E5 - - - D5 - - - |"
            " E5 - - - - - - - - - - - B4 - - - |"
            " C#5 - - - - - - - - - - - - - - - |"
            " . . . . . . . . A4 - - - C#5 - - - |"
            " F#5 - - - - - - - E5 - - - F#5 - - - |"
            " G#5 - - - - - - - - - - - B5 - - - |"
            " A5 - - - - - - - G#5 - - - - - - - |"
            " E#5 - - - - - - - G#5 - - - . . . .",
            SYNTH,
        ),
    ),
)

SONG_LAYERS = tuple(
    Song(f"boarded_up_{n}", SONG.bpm, SONG.parts[:n])
    for n in range(1, len(SONG.parts) + 1)
)


def round_song(round_number: int) -> Song:
    """The song with one part per round reached, all of it from the fourth
    round on."""
    return SONG_LAYERS[min(max(round_number, 1), len(SONG_LAYERS)) - 1]


BETWEEN_ROUNDS = SONG_LAYERS[0]

GAME_OVER = Song(
    name="boarded_up_game_over",
    bpm=84,
    loop=False,
    parts=(
        Part(
            "F#4 - - G#4 - - A4 - - C#5 - - - - - - |"
            " A4 - - - - - - - G#4 - - - - - - -",
            RIFF,
        ),
        Part(
            "F#3+A3+C#4 - - - - - - - - - - - - - - - |"
            " D3+F#3+A3 - - - - - - - C#3+E#3+G#3 - - - - - - -",
            CLUSTER,
            arp_speed=18.0,
        ),
        Part(
            "F#2 - - - - - - - - - - - - - - - | D2 - - - - - - - C#2 - - - - - - -",
            DEEP,
        ),
        Part("b . . . . . . . . . . . . . . . | b . . . . . . . b . . . . . . .", BOOM),
    ),
)

GAME_OVER_SECOND_BAR = GAME_OVER.seconds / 2
