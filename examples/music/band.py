"""A band: all four channels, arranged with plain Python.

The chip has four channels, so a song has up to four parts: here a lead, a
chord arpeggio, a bass and drums. Patterns are only strings, so ordinary
functions build the repetitive parts, and the lead is written out in full.
"""

from qade_engine.audio import Part, Sfx, Song

from .drums import KIT

LEAD = Sfx("square", duty=0.25, decay=0.8, wobble=0.01, wobble_hz=6.0, bits=6, vol=0.5)
CHORDS = Sfx("square", duty=0.125, decay=0.5, bits=5, vol=0.2)
BASS = Sfx("tri", decay=0.5, bits=8, vol=0.7)

# Am, F, C and G, a bar each: (chord, its root).
PROGRESSION = [
    ("A3+C4+E4", "A"),
    ("F3+A3+C4", "F"),
    ("C4+E4+G4", "C"),
    ("G3+B3+D4", "G"),
]


def whole_bar(chord: str) -> str:
    """A chord held for a whole bar of 16 steps."""
    return " ".join([chord, *["-"] * 15])


def bouncing(root: str) -> str:
    """A bar of 8th notes, bouncing between a root and the octave above."""
    return " ".join([f"{root}2", ".", f"{root}3", "."] * 4)


SONG = Song(
    name="band",
    bpm=128,
    parts=(
        Part(
            "A4 - - - C5 - E5 - - - D5 - C5 - B4 - |"
            " A4 - - - - - - - F4 - A4 - C5 - - - |"
            " G4 - - - C5 - E5 - G5 - - - E5 - C5 - |"
            " D5 - - - - - - - B4 - - - . . . .",
            LEAD,
            gate=0.9,
        ),
        Part(" | ".join(whole_bar(chord) for chord, _ in PROGRESSION), CHORDS),
        Part(" | ".join(bouncing(root) for _, root in PROGRESSION), BASS, gate=0.6),
        # One bar of drums, repeated under all four.
        Part("k . h . s . h . k . h k s . h .", KIT),
    ),
)
