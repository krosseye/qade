# SPDX-License-Identifier: GPL-3.0-or-later
"""Baked sound as WAV: in memory for effects, on disk for songs."""

import io
import os
import wave
from pathlib import Path

import numpy as np

from qade_engine.persistence import SAVE_ROOT

from .synth import RATE

DEFAULT_CACHE = SAVE_ROOT / "sfx_cache"


def wav_bytes(pcm: np.ndarray) -> bytes:
    """Mono 16-bit samples at ``RATE``, as a whole WAV file."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.astype(np.int16).tobytes())
    return buffer.getvalue()


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
        partial.write_bytes(wav_bytes(pcm))
        os.replace(partial, path)
    except OSError:
        partial.unlink(missing_ok=True)
        raise
