"""Drums: a kit names its sounds, and a short part repeats.

A kit is a dict of drum names to ``Sfx``. In a kit part, each token is a
drum's name, and the drum keeps its own pitch and length.

A part shorter than the song repeats to fill it, as long as its length
divides the song's: here a one-bar beat plays twice under a two-bar bass.
"""

from qade_engine.audio import Part, Sfx, Song

KIT = {
    # Kick: a low thump, falling in pitch.
    "k": Sfx("tri", 150, sweep=40, dur=0.12, decay=2.0, bits=8, vol=0.8),
    # Snare: a short burst of noise.
    "s": Sfx("noise", 3000, sweep=1500, dur=0.12, decay=2.5, bits=4, vol=0.4),
    # Hi-hat: a tick of high hiss.
    "h": Sfx("noise", 9000, dur=0.03, decay=3.0, bits=4, vol=0.15),
}

BASS = Sfx("tri", decay=0.6, bits=8, vol=0.7)

SONG = Song(
    name="drums",
    bpm=110,
    parts=(
        Part("k . h . s . h . k . h k s . h .", KIT),
        Part(
            "E2 . E3 . E2 . E3 . G2 . G3 . A2 . A3 . |"
            " E2 . E3 . E2 . E3 . D2 . D3 . B1 . B2 .",
            BASS,
            # Each note sounds for half its step: short and punchy.
            gate=0.5,
        ),
    ),
)
