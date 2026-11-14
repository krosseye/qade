# SPDX-License-Identifier: GPL-3.0-or-later
"""Game loop, fixed-step timing and phase timing under hostile clocks."""

import math
import random

import pytest
from PySide6.QtGui import QPainter
from support import (
    FakeApp,
    blank_image,
    define,
    run_for,
    to_playing,
)

from qade_engine import Event, Phase
from qade_engine.core.spring import spring_step
from qade_engine.core.state_machine import Edge, StateMachine, TransitionStyle
from qade_engine.core.timestep import FixedTimestep
from qade_engine.graphics.palette import WHITE
from qade_engine.graphics.particles import ParticleEffect
from qade_engine.host.host import MAX_FRAME_DT
from qade_engine.perf import FrameStats

STEP = 1 / 64


# --- FixedTimestep ----------------------------------------------------------


@pytest.mark.parametrize(
    "pattern",
    [
        [STEP] * 500,  # perfectly paced
        [STEP / 3] * 1500,  # display much faster than the sim
        [STEP * 7.3] * 70,  # display much slower than the sim
        [0.0] * 100 + [1.0],  # stalls, then one lump
        [1e-9] * 10_000,  # timer firing on top of itself
        [STEP - 1e-12, 2e-12] * 300,  # straddles every step boundary
    ],
    ids=["paced", "fast", "slow", "stall-then-lump", "femto", "boundary-straddle"],
)
def test_fixed_timestep_conserves_time(pattern):
    """Guards against drift: steps run must equal elapsed / step over any jitter."""
    ts = FixedTimestep(STEP)
    total = sum(ts.advance(dt) for dt in pattern)
    expected = sum(pattern) / STEP
    assert abs(total - expected) <= 1 + 1e-9
    assert 0.0 <= ts.alpha < 1.0


def test_fixed_timestep_random_jitter_never_drifts():
    rng = random.Random(7)
    ts = FixedTimestep(STEP)
    elapsed = steps = 0.0
    for _ in range(10_000):
        dt = rng.choice((0.0, rng.uniform(0, 0.05), rng.expovariate(60)))
        elapsed += dt
        steps += ts.advance(dt)
        assert 0.0 <= ts.alpha < 1.0
    assert abs(steps - elapsed / STEP) <= 1


def test_fixed_timestep_zero_elapsed_is_idempotent():
    ts = FixedTimestep(STEP)
    ts.advance(STEP * 0.4)
    alpha = ts.alpha
    for _ in range(1000):
        assert ts.advance(0.0) == 0
    assert ts.alpha == alpha


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -0.001, -1e308])
def test_fixed_timestep_ignores_bad_clock_readings(bad):
    """One NaN, infinite or backwards reading must add nothing and poison nothing."""
    ts = FixedTimestep(STEP)
    ts.advance(STEP * 0.5)
    assert ts.advance(bad) == 0
    assert ts.alpha == 0.5
    assert ts.advance(STEP * 0.5) == 1


# --- Host tick --------------------------------------------------------------


@pytest.fixture
def running(host):
    """A host with a FakeApp running, and the app."""
    app_holder: list[FakeApp] = []

    def create(services):
        app_holder.append(FakeApp(services))
        return app_holder[-1]

    host.switch_to(define(create))
    return host, app_holder[0]


@pytest.mark.parametrize(
    "frame_times",
    [
        [1 / 60] * 120,
        [1 / 144] * 288,
        [1 / 30] * 60,
        [0.004, 0.030] * 60,  # alternating jitter
        [0.0] * 50,
    ],
    ids=["60hz", "144hz", "30hz", "jitter", "frozen-clock"],
)
def test_host_steps_are_fixed_length_whatever_the_frame_rate(
    running, clock, frame_times
):
    host, app = running
    for dt in frame_times:
        clock.advance(dt)
        host.tick()
    assert set(app.step_dts) <= {STEP}
    # 1e-6: the fake clock itself accumulates float error at t=1000s.
    assert abs(len(app.step_dts) - sum(frame_times) / STEP) <= 1 + 1e-6


@pytest.mark.parametrize("hitch", [0.26, 1.0, 60.0, 86_400.0, 1e12])
def test_host_caps_catch_up_after_a_hitch(running, clock, hitch):
    """Guards against the spiral of death: a stall never runs more than MAX_FRAME_DT."""
    host, app = running
    cap = int(MAX_FRAME_DT / STEP)

    def tripwire(a: FakeApp) -> None:
        # Without the cap a 1e12 s hitch would loop ~1e14 times: fail fast instead.
        if len(a.step_dts) > cap:
            raise RuntimeError("catch-up not capped")

    app.on_step = tripwire
    clock.advance(hitch)
    host.tick()
    assert len(app.step_dts) == cap


def test_host_suspended_runs_no_steps_and_skips_time_away(running, clock):
    host, app = running
    host.set_suspended(True)
    for _ in range(100):
        clock.advance(0.1)
        host.tick()
    assert "step" not in app.calls
    host.set_suspended(False)
    clock.advance(STEP / 2)
    host.tick()
    assert "step" not in app.calls  # ten seconds away bought no catch-up steps


def test_host_resume_without_intervening_tick_does_not_catch_up(running, clock):
    host, app = running
    host.set_suspended(True)
    clock.advance(10.0)  # e.g. the event loop blocked in a modal OS loop
    host.set_suspended(False)
    host.tick()
    assert "step" not in app.calls


def test_host_suspend_and_resume_are_idempotent(running):
    host, app = running
    for _ in range(3):
        host.set_suspended(True)
    for _ in range(3):
        host.set_suspended(False)
    assert app.calls.count("suspend") == 1
    assert app.calls.count("resume") == 1


def test_switching_apps_while_suspended_suspends_the_new_app(host):
    host.set_suspended(True)
    apps: list[FakeApp] = []
    host.switch_to(define(lambda s: apps.append(FakeApp(s)) or apps[-1]))
    assert apps[0].calls == ["start", "suspend"]


def test_host_alpha_reaches_draw_in_unit_range(running, clock):
    """Frame.alpha is the interpolation factor; outside [0, 1) motion overshoots."""
    host, app = running
    seen: list[float] = []
    app.on_draw = lambda frame: seen.append(frame.alpha)
    image = blank_image(80, 60)
    for dt in (0.0, STEP * 0.5, STEP * 0.999, STEP * 3.25, 5.0):
        clock.advance(dt)
        host.tick()
        painter = QPainter(image)
        host.paint(painter, (80, 60))
        painter.end()
    assert seen and all(0.0 <= a < 1.0 for a in seen)


# --- ArcadeGame phases on simulation time ---------------------------------


def test_fade_switches_phase_exactly_halfway(game):
    """The phase flips at the fade's midpoint, measured in steps, not wall time."""
    game.send(Event.CONFIRM)
    half = round(game.GAMEPLAY_FADE_TIME / 2 * game.tick_hz)
    run_for(game, (half - 1) / game.tick_hz)
    assert game.phase is Phase.STANDBY
    game.step(game.dt)
    assert game.phase is Phase.INTRO
    assert game.transition is not None


def test_one_giant_step_through_a_fade_changes_phase_once(game):
    """A huge dt must switch and finish the fade in one go, firing hooks once."""
    to_playing(game)
    game.died()
    resets_before = game.log.count("reset")
    game.send(Event.CONFIRM)  # GAME_OVER -> fade -> PLAYING
    game.step(1e6)
    assert game.phase is Phase.PLAYING
    assert game.transition is None
    assert game.log.count("reset") == resets_before + 1


def test_zero_dt_steps_freeze_transitions_and_timeouts(game):
    to_playing(game)
    game.died()
    game.send(Event.CONFIRM)
    for _ in range(10_000):
        game.step(0.0)
    assert game.phase is Phase.GAME_OVER
    assert game.transition is not None and game.transition.elapsed == 0.0


def test_game_over_times_out_to_standby_on_sim_time(game):
    to_playing(game)
    game.died()
    run_for(game, game.GAME_OVER_IDLE_TIMEOUT - game.dt)
    assert game.transition is None
    game.step(game.dt)
    assert game.transition is not None and game.transition.target is Phase.STANDBY
    run_for(game, game.STANDBY_FADE_TIME)
    assert game.phase is Phase.STANDBY and game.transition is None


@pytest.mark.parametrize("dt", [STEP, 1.0, 1e9])
def test_zero_duration_edge_is_instant_and_never_divides_by_zero(dt):
    """A styled edge with duration 0 must cut instantly, not build a 0s Transition."""
    machine = StateMachine(
        Phase.STANDBY,
        {
            (Phase.STANDBY, Event.CONFIRM): Edge(
                Phase.INTRO, style=TransitionStyle.FADE, duration=0.0
            )
        },
        timeout_event=Event.TIMEOUT,
    )
    assert machine.send(Event.CONFIRM)
    assert machine.state is Phase.INTRO and machine.transition is None
    machine.advance(dt)


# --- Pause ------------------------------------------------------------------


def test_pause_freezes_the_whole_simulation(game):
    to_playing(game)
    effect = ParticleEffect(50, (5.0, 5.0), (WHITE, WHITE), speed=(50, 90))
    game.particles.emit((effect,), 100, 100)
    run_for(game, 0.5)
    game.send(Event.PAUSE)

    elapsed, steps = game.elapsed, game.playing_steps
    stars = [(s.x, s.y) for s in game.starfield.stars]
    particles = [(p.x, p.y, p.life) for p in game.particles.items]
    run_for(game, 120.0)  # long enough to trip any timeout

    assert game.phase is Phase.PAUSED
    assert (game.elapsed, game.playing_steps) == (elapsed, steps)
    assert [(s.x, s.y) for s in game.starfield.stars] == stars
    assert [(p.x, p.y, p.life) for p in game.particles.items] == particles

    game.send(Event.PAUSE)
    game.step(game.dt)
    assert game.playing_steps == steps + 1
    assert game.elapsed == pytest.approx(elapsed + game.dt)


@pytest.mark.parametrize("presses", [2, 3, 50, 51])
def test_rapid_pause_toggling_lands_on_parity(game, presses):
    to_playing(game)
    for _ in range(presses):
        game.send(Event.PAUSE)
    assert game.phase is (Phase.PAUSED if presses % 2 else Phase.PLAYING)


@pytest.mark.parametrize("phase_driver", ["standby", "intro", "game_over"])
def test_pause_is_ignored_outside_a_run(game, phase_driver):
    if phase_driver != "standby":
        game.send(Event.CONFIRM)
        run_for(game, game.GAMEPLAY_FADE_TIME)
    if phase_driver == "game_over":
        game.send(Event.CONFIRM)
        run_for(game, game.GAMEPLAY_FADE_TIME)
        game.died()
    before = game.phase
    assert not game.send(Event.PAUSE)
    assert game.phase is before


def test_suspend_pauses_a_run_and_resume_leaves_it_paused(game):
    to_playing(game)
    game.suspend()
    assert game.phase is Phase.PAUSED
    game.resume()
    assert game.phase is Phase.PAUSED  # the player decides when play resumes


def test_suspend_while_already_paused_does_not_unpause(game):
    """Suspend sends PAUSE only when PLAYING; a toggle would resume a paused run."""
    to_playing(game)
    game.send(Event.PAUSE)
    game.suspend()
    game.resume()
    assert game.phase is Phase.PAUSED


# --- Spring -----------------------------------------------------------------


@pytest.mark.parametrize("frequency_dt", [0.01, 0.1, 0.3, 0.5, 0.7])
@pytest.mark.parametrize("target", [1.0, -250.0, 1e6])
def test_spring_settles_without_overshoot(frequency_dt, target):
    value = velocity = 0.0
    frequency = frequency_dt / STEP
    steps = int(12 / frequency / STEP) + 10
    for _ in range(steps):
        value, velocity = spring_step(value, velocity, target, frequency, STEP)
        assert abs(value) <= abs(target) * (1 + 1e-9)
    assert value == pytest.approx(target, rel=1e-3)


def test_spring_zero_dt_is_a_no_op():
    assert spring_step(3.0, 2.0, 10.0, 40.0, 0.0) == (3.0, 2.0)


def test_spring_at_rest_on_target_stays_put():
    assert spring_step(5.0, 0.0, 5.0, 60.0, STEP) == (5.0, 0.0)


@pytest.mark.parametrize("frequency_dt", [0.9, 1.0, 2.0, 5.0, 1e3])
def test_spring_is_stable_and_never_overshoots_for_any_step(frequency_dt):
    """Stiff springs at long steps used to diverge from frequency * dt ~ 0.85."""
    value = velocity = 0.0
    for _ in range(5000):
        value, velocity = spring_step(value, velocity, 1.0, frequency_dt / STEP, STEP)
        assert 0.0 <= value <= 1.0 + 1e-12
    assert value == pytest.approx(1.0)


def test_spring_retargeting_keeps_velocity():
    """Moving the target mid-motion must not jolt the velocity."""
    _, velocity = spring_step(0.0, 3.0, 10.0, 8.0, 0.0)
    assert velocity == 3.0
    _, v_a = spring_step(2.0, 3.0, 10.0, 8.0, 1e-9)
    _, v_b = spring_step(2.0, 3.0, -10.0, 8.0, 1e-9)
    assert v_a == pytest.approx(3.0, abs=1e-5) and v_b == pytest.approx(3.0, abs=1e-5)


# --- Frame statistics -------------------------------------------------------


def test_frame_stats_report_a_single_hitch_despite_a_healthy_average():
    now = [0.0]
    stats = FrameStats(window=1.0, clock=lambda: now[0])
    stats.tick()
    for dt in [1 / 60] * 59 + [0.25]:
        now[0] += dt
        stats.tick()
    assert stats.worst_ms == pytest.approx(250.0)
    assert stats.avg_ms < 25.0


def test_frame_stats_rate_decays_to_zero_when_nothing_happens():
    now = [0.0]
    stats = FrameStats(window=0.5, clock=lambda: now[0])
    stats.tick()
    for _ in range(60):
        now[0] += 1 / 60
        stats.tick()
    assert stats.rate > 0
    for _ in range(60):
        now[0] += 1 / 60
        stats.tick(0)
    assert stats.rate == 0.0 and stats.avg_ms == 0.0


def test_tick_count_advances_even_while_paused(game):
    """Documents that tick_count is a step counter, not a play-time counter."""
    to_playing(game)
    game.send(Event.PAUSE)
    before = game.tick_count
    run_for(game, 1.0)
    assert game.tick_count == before + game.tick_hz
