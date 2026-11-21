# SPDX-License-Identifier: GPL-3.0-or-later
import random

import pytest

from boarded_up.layout import DOOR_BASE, DOOR_STEP, ROOMS_X, ROOMS_Y, build_house


@pytest.mark.parametrize("seed", range(20))
def test_house_is_whole_and_priced_by_depth(seed: int) -> None:
    house = build_house(random.Random(seed))
    for door in house.doors:
        door.open = True
    reach = house.distances(
        next(t for t, r in house.room_of.items() if r == house.start)
    )
    assert {house.room_of[t] for t in reach if t in house.room_of} == set(
        house.room_of.values()
    )
    assert len(set(house.room_of.values())) == ROOMS_X * ROOMS_Y
    for door in house.doors:
        assert door.price == DOOR_BASE + DOOR_STEP * (
            max(house.depth[r] for r in door.rooms) - 1
        )
    assert any(w.room == house.start for w in house.windows)
    for room in set(house.room_of.values()):
        assert sum(room in door.rooms for door in house.doors) >= 2
