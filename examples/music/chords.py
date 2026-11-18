"""Chords: notes joined with ``+`` are played as an arpeggio.

A channel plays one note at a time, so a sound chip plays a chord by cycling
through its notes. ``arp_speed`` sets how fast, in notes a second: fast
blurs into a chord, slow is heard as a broken one.
"""

from qade_engine.audio import Part, Sfx, Song

# A thin square wave: the classic chip chord sound.
CHORDS = Sfx("square", duty=0.25, decay=0.3, bits=6, vol=0.4)

SONG = Song(
    name="chords",
    bpm=90,
    parts=(
        Part(
            # C, Am, F and G, two beats each.
            "C4+E4+G4 - - - - - - - A3+C4+E4 - - - - - - - |"
            " F3+A3+C4 - - - - - - - G3+B3+D4 - - - - - - -",
            CHORDS,
            arp_speed=24.0,
        ),
    ),
)
