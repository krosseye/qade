"""Notes, holds and rests: a tune on one instrument.

Each token in a pattern is one step: a 16th note, at the default four steps
a beat, so a bar of 4/4 is 16 steps. A note name starts a note, ``-`` holds
it for another step and ``.`` rests. ``|`` marks the bars, for reading only.
"""

from qade_engine.audio import Part, Sfx, Song

# An instrument is an ``Sfx``. Each note fills in its pitch and length.
FLUTE = Sfx("tri", decay=0.5, bits=8, vol=0.6)

SONG = Song(
    name="notes",
    bpm=100,
    parts=(
        Part(
            "C5 - - - E5 - - - G5 - - - E5 - - - |"
            " F5 - D5 - B4 - G4 - C5 - - - . . . .",
            FLUTE,
        ),
    ),
)
