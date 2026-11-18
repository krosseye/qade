"""A sting: ``loop=False`` makes a one-shot, for a level cleared or a game over.

A looping song is cut to exactly its length, its last notes' tails wrapped
round to its start so the loop has no seam. A one-shot instead lets its last
notes ring out, so it runs on past its steps.
"""

from qade_engine.audio import Part, Sfx, Song

BELL = Sfx("square", duty=0.5, decay=2.5, bits=6, vol=0.5)
BASS = Sfx("tri", decay=1.5, bits=8, vol=0.7)

SONG = Song(
    name="sting",
    bpm=140,
    loop=False,
    parts=(
        # A rising arpeggio that lands on the octave and rings.
        Part("C5 . E5 . G5 . C6 - - - - - - - - -", BELL),
        Part("C3 - - - - - - - C2 - - - - - - -", BASS),
    ),
)
