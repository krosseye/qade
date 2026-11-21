# SPDX-License-Identifier: GPL-3.0-or-later
import logging

import numpy as np
import sdl2
from sdl2 import sdlmixer as mix

from .cache import wav_bytes

_log = logging.getLogger(__name__)

_opened: bool | None = None
_channels = 0
_free: list[int] = []


def available() -> bool:
    """Opens the device on first use.

    Returns:
        Whether sound can play. A failure is logged once and remembered.
    """
    global _opened
    if _opened is None:
        _opened = _open()
    return _opened


def _open() -> bool:
    if (
        sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_AUDIO) < 0
        or mix.Mix_OpenAudioDevice(
            mix.MIX_DEFAULT_FREQUENCY, mix.MIX_DEFAULT_FORMAT, 2, 512, None, 0
        )
        < 0
    ):
        _log.error("no audio device: %s", error())
        return False
    mix.Mix_AllocateChannels(0)
    return True


def error() -> str:
    """SDL's last error message."""
    return sdl2.SDL_GetError().decode(errors="replace")


def take_channel() -> int:
    """A mixer channel for the caller alone, until ``release_channel``."""
    global _channels
    if not _free:
        _free.append(_channels)
        _channels += 1
        mix.Mix_AllocateChannels(_channels)
    return _free.pop()


def release_channel(channel: int) -> None:
    """Silences a channel and hands it back."""
    mix.Mix_HaltChannel(channel)
    _free.append(channel)


def load_chunk(pcm: np.ndarray):
    """Loads samples into the mixer, converted to the device's format.

    Args:
        pcm: Mono 16-bit samples at ``RATE``.

    Returns:
        The chunk. Free it with ``Mix_FreeChunk``.

    Raises:
        OSError: The mixer can't take it.
    """
    data = wav_bytes(pcm)
    chunk = mix.Mix_LoadWAV_RW(sdl2.SDL_RWFromConstMem(data, len(data)), 1)
    if not chunk:
        raise OSError(f"can't load a sound: {error()}")
    return chunk
