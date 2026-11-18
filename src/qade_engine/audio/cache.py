# SPDX-License-Identifier: GPL-3.0-or-later
"""Baked sound on disk: the WAV files QSoundEffect plays."""

import hashlib
import os
import wave
from pathlib import Path

import numpy as np

from qade_engine.persistence import SAVE_ROOT

from .synth import RATE

DEFAULT_CACHE = SAVE_ROOT / "sfx_cache"


def write_wav(pcm: np.ndarray, path: Path) -> None:
    """Writes mono 16-bit samples as a WAV.

    Args:
        pcm: Samples at ``RATE``.
        path: The file to write. Its folder is created if missing.

    Raises:
        OSError: The file can't be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(f".{os.getpid()}.part")
    try:
        with wave.open(str(partial), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm.astype(np.int16).tobytes())
        os.replace(partial, path)
    except OSError:
        partial.unlink(missing_ok=True)
        raise


def cached_wav(pcm: np.ndarray, cache_dir: Path) -> Path:
    """The cached WAV holding these samples, written if it isn't there yet.

    Args:
        pcm: Mono 16-bit samples at ``RATE``.
        cache_dir: Where baked sound is kept.

    Returns:
        The file, named by a hash of the samples.

    Raises:
        OSError: The file can't be written.
    """
    data = pcm.astype(np.int16).tobytes()
    path = cache_dir / f"{hashlib.sha1(data).hexdigest()}.wav"
    if not path.exists():
        write_wav(pcm, path)
    return path
