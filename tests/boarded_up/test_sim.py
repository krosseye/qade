# SPDX-License-Identifier: GPL-3.0-or-later
import random

import pytest

from boarded_up.layout import MAX_PLANKS, Door, House, Window, build_house
from boarded_up.sim import (
    BUY_TIME,
    CLIMB_GAP,
    CLIMB_TIME,
    LULL_TIME,
    PLANK_POINTS,
    PLANK_TIME,
    PLAYER_SPEED,
    WINDUP_TIME,
    Sim,
    Zombie,
    ZombieState,
    max_alive,
    outside_spot,
    round_size,
    spawn_interval,
    tear_time,
    toward,
    zombie_health,
    zombie_speed,
)

DT = 1 / 64


def quiet_sim(seed: int = 0) -> Sim:
    rng = random.Random(seed)
    sim = Sim(build_house(rng), rng)
    sim.lull = 1e9
    return sim


def run(sim: Sim, seconds: float, move=(0.0, 0.0), act=False) -> None:
    for _ in range(round(seconds / DT)):
        sim.step(DT, move, act)


def start_window(sim: Sim) -> Window:
    return next(w for w in sim.house.windows if w.room == sim.house.start)


def start_door(sim: Sim) -> Door:
    return next(d for d in sim.house.doors if sim.house.start in d.rooms)


def stand_by(sim: Sim, door: Door) -> None:
    """Put the player on the start room's side of a door touching it."""
    house: House = sim.house
    x, y = door.tiles[0]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if house.room_of.get((x + dx, y + dy)) == house.start:
            sim.x, sim.y = x + dx + 0.5, y + dy + 0.5
            return
    raise AssertionError("door doesn't touch the start room")


def chaser(sim: Sim, dx: float, dy: float, hp: int = 99) -> Zombie:
    z = Zombie(sim.x + dx, sim.y + dy, hp, None, state=ZombieState.CHASING)
    sim.zombies.append(z)
    return z


def test_holding_at_a_damaged_window_boards_it() -> None:
    sim = quiet_sim()
    window = start_window(sim)
    window.planks = 2
    sim.x, sim.y = window.inside[0] + 0.5, window.inside[1] + 0.5
    points = sim.points
    run(sim, PLANK_TIME * 0.9, act=True)
    assert window.planks == 2
    run(sim, PLANK_TIME * 0.2, act=True)
    assert window.planks == 3 and sim.points == points + PLANK_POINTS


def test_holding_at_an_affordable_door_buys_it() -> None:
    sim = quiet_sim()
    door = start_door(sim)
    stand_by(sim, door)
    sim.points = door.price + 5
    run(sim, BUY_TIME + 2 * DT, act=True)
    assert door.open and sim.points == 5
    assert set(door.rooms) <= sim.house.open_rooms


def test_at_a_door_you_cant_afford_the_button_shoots() -> None:
    sim = quiet_sim()
    door = start_door(sim)
    stand_by(sim, door)
    sim.points = door.price - 1
    z = chaser(sim, 0.0, 0.0)
    for dx, dy in ((2.5, 0), (-2.5, 0), (0, 2.5), (0, -2.5)):
        z.x, z.y = sim.x + dx, sim.y + dy
        if sim.house.passable((int(z.x), int(z.y))) and sim.sees(
            sim.x, sim.y, z.x, z.y
        ):
            break
    else:
        raise AssertionError("no spot in sight beside the door")
    sim.step(DT, (0, 0), True)
    assert not door.open
    assert len(sim.effects.shots) == 1 and z.hp == 98


def test_letting_go_runs_and_never_shoots() -> None:
    sim = quiet_sim()
    chaser(sim, 3.0, 0.0)
    x = sim.x
    run(sim, 6 * DT, move=(-1.0, 0.0))
    assert sim.x == pytest.approx(x - PLAYER_SPEED * 6 * DT)
    assert not sim.effects.shots and not sim.planted


def test_a_swipe_lands_only_after_its_warning() -> None:
    sim = quiet_sim()
    z = chaser(sim, -0.6, 0.0)
    sim.step(DT, (0, 0), False)
    assert z.windup > 0 and sim.hits == 0
    run(sim, WINDUP_TIME - 2 * DT)
    assert sim.hits == 0
    run(sim, 4 * DT)
    assert sim.hits == 1


def test_a_swipe_misses_if_you_get_clear_in_time() -> None:
    sim = quiet_sim()
    z = chaser(sim, -0.6, 0.0)
    sim.step(DT, (0, 0), False)
    run(sim, WINDUP_TIME + 4 * DT, move=(1.0, 0.0))
    assert z.windup <= 0 and sim.hits == 0


def test_planks_tear_off_one_at_a_time_then_the_zombie_climbs_in() -> None:
    sim = quiet_sim()
    sim.round = 1
    window = start_window(sim)
    z = Zombie(*outside_spot(window, 0), 99, window)
    sim.zombies.append(z)
    for planks in range(MAX_PLANKS - 1, -1, -1):
        run(sim, tear_time(1) + DT)
        assert window.planks == planks
    run(sim, CLIMB_GAP + CLIMB_TIME + 2 * DT)
    assert z.state is ZombieState.CHASING


def test_a_broken_window_lets_them_in_one_at_a_time_with_a_gap() -> None:
    sim = quiet_sim()
    sim.round = 1
    window = start_window(sim)
    window.planks = 0
    queue = [Zombie(*outside_spot(window, p), 99, window) for p in range(3)]
    sim.zombies += queue
    inside_at: dict[int, float] = {}
    for i in range(round(6.0 / DT)):
        sim.step(DT, (0, 0), False)
        for n, z in enumerate(queue):
            if z.state is ZombieState.CHASING and n not in inside_at:
                inside_at[n] = i * DT
    assert sorted(inside_at) == [0, 1, 2]
    for n in (1, 2):
        assert inside_at[n] - inside_at[n - 1] >= CLIMB_GAP + CLIMB_TIME - DT


@pytest.mark.parametrize("climbed, gets_in", [(0.2, False), (0.8, True)])
def test_a_plank_nailed_mid_climb_turns_back_only_the_outer_half(
    climbed: float, gets_in: bool
) -> None:
    sim = quiet_sim()
    sim.round = 1
    window = start_window(sim)
    window.planks = 0
    z = Zombie(*outside_spot(window, 0), 99, window)
    sim.zombies.append(z)
    run(sim, CLIMB_GAP + DT + CLIMB_TIME * climbed)
    assert z.state is ZombieState.CLIMBING
    window.planks = 1
    run(sim, CLIMB_TIME)
    assert (z.state is ZombieState.CHASING) == gets_in
    assert window.planks == 1


@pytest.mark.parametrize("seed", range(5))
def test_the_whole_queue_outside_a_window_can_be_shot(seed: int) -> None:
    sim = quiet_sim(seed)
    for window in sim.house.windows:
        (ix, iy), (ox, oy) = window.inside, window.outward
        # Two tiles in from the window, out of reach to board it.
        sim.x, sim.y = ix - 2 * ox + 0.5, iy - 2 * oy + 0.5
        for place in range(3):
            assert sim.sees(sim.x, sim.y, *outside_spot(window, place))


@pytest.mark.parametrize("seed", range(5))
def test_zombies_spawn_only_at_windows_of_open_rooms(seed: int) -> None:
    sim = quiet_sim(seed)
    sim.round = 1
    for _ in range(50):
        sim._spawn()
        z = sim.zombies.pop()
        assert z.window is not None and z.window.room in sim.house.open_rooms


def test_a_round_ends_only_when_all_are_spawned_and_dead() -> None:
    sim = quiet_sim()
    sim.lull = 0.0
    sim.step(DT, (0, 0), False)
    assert sim.round == 1 and sim.to_spawn == round_size(1)
    sim.to_spawn = 0
    straggler = chaser(sim, 30.0, 30.0)
    run(sim, 10.0)
    assert sim.round == 1
    sim.zombies.remove(straggler)
    run(sim, LULL_TIME + 0.5)
    assert sim.round == 2


def test_the_last_kill_of_a_round_clears_it_once() -> None:
    sim = quiet_sim()
    sim.lull = 0.0
    sim.step(DT, (0, 0), False)
    sim.to_spawn = 0
    chaser(sim, 2.0, 0.0, hp=1)
    sim.step(DT, (0, 0), True)
    assert not sim.zombies and sim.effects.round_cleared
    sim.step(DT, (0, 0), True)
    assert not sim.effects.round_cleared


@pytest.mark.parametrize("first, limit", [(2.0, 10.0), (10.0, 2.0)])
def test_toward_starts_at_first_and_closes_on_limit_without_passing_it(
    first: float, limit: float
) -> None:
    values = [toward(n, first, limit, 3) for n in range(1, 500)]
    assert values[0] == first
    rising = limit > first
    assert values == sorted(values, reverse=not rising)
    assert all((v <= limit) if rising else (v >= limit) for v in values)


def test_every_round_is_at_least_as_hard_as_the_last() -> None:
    rounds = range(1, 500)
    for curve, rising in (
        (zombie_speed, True),
        (zombie_health, True),
        (max_alive, True),
        (round_size, True),
        (spawn_interval, False),
        (tear_time, False),
    ):
        values = [curve(n) for n in rounds]
        assert values == sorted(values, reverse=not rising), curve.__name__


@pytest.mark.parametrize("n", [1, 10, 100, 10_000])
def test_the_horde_stays_beatable_however_long_you_last(n: int) -> None:
    assert zombie_speed(n) < PLAYER_SPEED
    assert spawn_interval(n) > 0 and tear_time(n) > 0
    assert zombie_health(n) >= 1 and max_alive(n) >= 1


@pytest.mark.parametrize("seed", range(5))
def test_standing_still_holds_the_opening_rounds_but_not_for_long(seed: int) -> None:
    rng = random.Random(seed)
    sim = Sim(build_house(rng), rng)
    while not sim.downed:
        sim.step(1 / 30, (0, 0), True)  # never move, always hold the button
    assert 4 <= sim.round <= 7
