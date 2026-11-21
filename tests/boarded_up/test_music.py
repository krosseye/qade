# SPDX-License-Identifier: GPL-3.0-or-later
from boarded_up import music


def test_the_song_gains_a_part_a_round_until_whole() -> None:
    parts = [len(music.round_song(n).parts) for n in range(8)]
    assert parts == [1, 1, 2, 3, 4, 4, 4, 4]
    assert music.round_song(99).parts == music.SONG.parts
