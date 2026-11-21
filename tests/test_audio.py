# SPDX-License-Identifier: GPL-3.0-or-later
import time

import numpy as np
import pytest
from sdl2 import sdlmixer as mix
from support import FakeClock

from qade_engine.audio import Sfx, SoundBus
from qade_engine.audio.cache import write_wav
from qade_engine.audio.music import MusicTrack
from qade_engine.audio.synth import RATE

BEEP = Sfx("square", 440, dur=0.5)
HUM = Sfx("tri", 220, dur=0.5, decay=0, loop=True)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def bus(clock):
    bus = SoundBus(max_voices=2, clock=clock)
    yield bus
    bus.close()


def playing(bus: SoundBus, name: str) -> int:
    return sum(bool(mix.Mix_Playing(v.channel)) for v in bus._sounds[name].voices)


def test_a_registered_sound_plays_and_stops(bus):
    bus.register("beep", BEEP)
    assert bus.play("beep")
    assert playing(bus, "beep") == 1
    bus.stop("beep")
    assert playing(bus, "beep") == 0


def test_an_unknown_sound_is_ignored(bus):
    assert not bus.play("nothing")


def test_a_gap_drops_triggers_too_close_together(bus, clock):
    bus.register("beep", BEEP, gap=0.1)
    assert bus.play("beep")
    clock.advance(0.05)
    assert not bus.play("beep")
    clock.advance(0.1)
    assert bus.play("beep")


def test_a_full_bus_cuts_lower_priority_and_drops_lower_priority(bus):
    bus.register("low", BEEP, voices=2, priority=0)
    bus.register("high", BEEP, voices=1, priority=2)
    bus.register("normal", BEEP, voices=1, priority=1)
    assert bus.play("low") and bus.play("low")
    assert bus.play("high")
    assert playing(bus, "low") == 1 and playing(bus, "high") == 1
    assert bus.play("normal")
    assert playing(bus, "low") == 0
    bus.register("ambient", BEEP, voices=1, priority=0)
    assert not bus.play("ambient")


def test_a_loop_plays_once_until_stopped(bus):
    bus.register("hum", HUM)
    assert bus.play("hum") and bus.play("hum")
    assert playing(bus, "hum") == 1
    bus.stop_loops()
    assert playing(bus, "hum") == 0


def test_closing_frees_channels_for_the_next_bus(clock):
    first = SoundBus(clock=clock)
    first.register("beep", BEEP, voices=3)
    channels = {v.channel for v in first._voices}
    first.close()
    second = SoundBus(clock=clock)
    second.register("beep", BEEP, voices=3)
    assert {v.channel for v in second._voices} == channels
    second.close()


def wav(tmp_path, seconds: float):
    path = tmp_path / f"{seconds}.wav"
    write_wav(np.full(int(RATE * seconds), 1000, np.int16), path)
    return path


def wait_until(condition, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > end:
            return False
        time.sleep(0.01)
    return True


def test_music_carries_on_from_where_it_stopped(tmp_path):
    track = MusicTrack(wav(tmp_path, 5.0))
    try:
        track.start()
        assert wait_until(lambda: mix.Mix_GetMusicPosition(track._music) > 0.1)
        track.stop()
        assert mix.Mix_PausedMusic()
        paused_at = mix.Mix_GetMusicPosition(track._music)
        track.start()
        assert not mix.Mix_PausedMusic()
        assert mix.Mix_GetMusicPosition(track._music) >= paused_at
    finally:
        track.close()


def test_a_one_shot_finishes_and_will_not_replay(tmp_path):
    track = MusicTrack(wav(tmp_path, 0.1), loop=False)
    try:
        track.start()
        assert wait_until(lambda: track.finished)
        track.start()
        assert not mix.Mix_PlayingMusic()
    finally:
        track.close()


def test_a_track_cut_off_by_another_starts_again_from_the_top(tmp_path):
    first = MusicTrack(wav(tmp_path, 5.0))
    second = MusicTrack(wav(tmp_path, 4.0))
    try:
        first.start()
        first.stop()
        second.start()
        first.start()
        assert not mix.Mix_PausedMusic()
        assert mix.Mix_GetMusicPosition(first._music) < 0.1
        assert not second.finished
    finally:
        first.close()
        second.close()
