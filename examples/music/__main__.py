"""Bakes each example song to a WAV file to listen to.

python -m examples.music [OUT_DIR]
"""

import sys
from pathlib import Path

from qade_engine.audio import bake_song
from qade_engine.audio.cache import write_wav

from . import band, chords, drums, notes, sting

out = Path(sys.argv[1] if len(sys.argv) > 1 else "songs")
for example in (notes, chords, drums, band, sting):
    path = out / f"{example.SONG.name}.wav"
    write_wav(bake_song(example.SONG), path)
    print(f"{path}: {example.SONG.seconds:.1f}s")
