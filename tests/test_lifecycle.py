# SPDX-License-Identifier: GPL-3.0-or-later
"""Lifecycle: app switching, fault isolation, re-entrancy, pools, leaks and saves."""

import gc
import json
import math
import random
import weakref

import pytest
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QColor
from support import FakeApp, ProbeGame, define, run_for, to_playing

from qade_engine import Event, HighScoreStore, Phase
from qade_engine.graphics import current_theme
from qade_engine.graphics.palette import WHITE
from qade_engine.graphics.particles import ParticleEffect, ParticleSystem, Shape
from qade_engine.graphics.starfield import StarField
from qade_engine.graphics.theme import oklch
from qade_engine.host.app import GameDefinition, GameInfo, Services
from qade_engine.input import InputMap

DOT = ParticleEffect(10, (0.5, 1.0), (WHITE, WHITE), speed=(10, 100))


def drain_events() -> None:
    """Runs deferred host requests (they ride a zero-length single-shot timer)."""
    for _ in range(3):
        QCoreApplication.processEvents()


class Apps:
    """A GameDefinition factory that remembers every app it built."""

    def __init__(self, game_id: str = "fake", configure=None):
        self.built: list[FakeApp] = []
        self.configure = configure
        self.definition = define(self.create, game_id)

    def create(self, services: Services) -> FakeApp:
        app = FakeApp(services)
        if self.configure:
            self.configure(app)
        self.built.append(app)
        return app

    @property
    def last(self) -> FakeApp:
        return self.built[-1]


# --- Host: fault isolation ----------------------------------------------------


def test_a_raising_step_is_the_last_call_the_app_ever_gets(host, clock):
    apps = Apps()
    host.switch_to(apps.definition)
    app = apps.last
    app.fail_in = "step"
    clock.advance(0.2)  # many steps due: the loop must stop at the first failure
    host.tick()
    clock.advance(0.2)
    host.tick()
    host.set_suspended(True)
    host.set_suspended(False)
    host._on_action("confirm")
    assert app.calls.count("step") == 1
    assert not {"suspend", "resume"} & set(app.calls)
    assert ("action", "confirm") not in app.calls


def test_a_failed_app_is_left_for_home_and_stopped(host, clock):
    home, game = Apps("home"), Apps("game")
    host.home = home.definition
    host.switch_to(game.definition)
    game.last.fail_in = "step"
    clock.advance(0.05)
    host.tick()
    assert "stop" not in game.last.calls  # never stopped mid-tick
    drain_events()
    assert game.last.calls[-1] == "stop"
    assert host.info == home.definition.info
    assert home.last.calls == ["start"]


def test_a_raising_stop_does_not_block_the_switch(host):
    first, second = Apps("a"), Apps("b")
    host.switch_to(first.definition)
    first.last.fail_in = "stop"
    host.switch_to(second.definition)
    assert host.app is second.last


def test_a_failing_constructor_leaves_the_running_app_untouched(host, clock):
    good = Apps("good")
    host.switch_to(good.definition)

    def explode(services):
        raise RuntimeError("bad game")

    with pytest.raises(RuntimeError):
        host.switch_to(define(explode, "bad"))
    assert host.app is good.last and "stop" not in good.last.calls
    clock.advance(0.05)
    host.tick()
    assert "step" in good.last.calls


def test_an_app_without_quit_is_rejected_before_anything_changes(host):
    good = Apps("good")
    host.switch_to(good.definition)
    no_quit = define(lambda s: FakeApp(s, InputMap()), "noquit")
    with pytest.raises(ValueError, match="quit"):
        host.switch_to(no_quit)
    assert host.app is good.last and good.last.calls == ["start"]


def test_shutdown_is_idempotent(host):
    apps = Apps()
    host.switch_to(apps.definition)
    host.shutdown()
    host.shutdown()
    assert apps.last.calls.count("stop") == 1


# --- Host: mutation from inside a step ---------------------------------------


def test_exit_requested_mid_step_waits_for_the_tick_to_finish(host, clock):
    """Guards against an app being torn down inside its own step loop."""
    home, game = Apps("home"), Apps("game")
    host.home = home.definition
    host.switch_to(game.definition)
    game.last.on_step = lambda app: app.services.exit()
    clock.advance(0.1)
    host.tick()
    steps = game.last.calls.count("step")
    assert steps > 1  # the rest of the tick still ran
    assert "stop" not in game.last.calls
    drain_events()
    assert host.info == home.definition.info


def test_only_the_last_request_before_the_tick_ends_counts(host, clock):
    home, game, other = Apps("home"), Apps("game"), Apps("other")
    host.home = home.definition

    def flip_flop(app):
        app.services.exit()
        app.services.launch(other.definition)

    host.switch_to(game.definition)
    game.last.on_step = flip_flop
    clock.advance(0.1)
    host.tick()
    drain_events()
    assert host.info == other.definition.info
    assert home.built == []  # home was never even built
    assert len(other.built) == 1


def test_launching_the_same_game_repeatedly_builds_fresh_instances(host):
    apps = Apps()
    for _ in range(5):
        host.switch_to(apps.definition)
    assert len({id(a) for a in apps.built}) == 5
    assert all(a.calls == ["start", "stop"] for a in apps.built[:-1])


# --- Leaks ---------------------------------------------------------------------


def test_switched_out_arcade_games_are_garbage_collected(host, store):
    """Signal connections, timers and lambdas must not pin old games in memory."""
    refs: list[weakref.ref] = []

    def create(services):
        game = ProbeGame(services, store)
        refs.append(weakref.ref(game))
        return game

    definition = define(create, "probe")
    for _ in range(20):
        host.switch_to(definition)
        to_playing(host.app)  # type: ignore[arg-type]
    gc.collect()
    alive = [r for r in refs if r() is not None]
    assert alive == [refs[-1]]


def test_stopping_a_game_stops_every_intro_timer(game):
    game.start()
    game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    intro = game._intro
    assert intro is not None and any(t.isActive() for t in intro.findChildren(QTimer))
    game.stop()
    assert not any(t.isActive() for t in intro.findChildren(QTimer))


def test_start_stop_cycles_are_safe(game):
    for _ in range(10):
        game.start()
        game.stop()
    game.stop()  # an extra stop must not raise


# --- ArcadeGame flow integrity -------------------------------------------------


def test_hooks_run_in_order_setup_then_reset(game):
    assert game.log == ["setup", "reset"]


def test_double_confirm_during_a_fade_cannot_skip_the_intro(game):
    game.send(Event.CONFIRM)
    for _ in range(20):
        assert not game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    assert game.phase is Phase.INTRO


def test_death_cuts_through_a_running_fade(game):
    """Nothing can lose a player's death, even mid-transition."""
    to_playing(game)
    game.died()
    game.send(Event.CONFIRM)  # fade back into a fresh run
    run_for(game, game.GAMEPLAY_FADE_TIME * 0.6)  # past the halfway switch
    assert game.phase is Phase.PLAYING and game.transition is not None
    game.died()
    assert game.phase is Phase.GAME_OVER and game.transition is None


def test_dying_twice_in_one_step_records_once(services, tmp_path):
    saves: list[int] = []

    class Spy(HighScoreStore):
        def save(self, score: int) -> None:
            saves.append(score)
            super().save(score)

    game = ProbeGame(services, Spy(tmp_path / "hs.json"))
    to_playing(game)
    game.score = 10
    game.died()
    game.died()
    assert game.phase is Phase.GAME_OVER and saves == [10]


def test_reentrant_death_from_reset_lands_in_game_over(services, store):
    """A hook that sends an event while the phase is changing must not corrupt the flow."""

    class Cursed(ProbeGame):
        def reset(self) -> None:
            super().reset()
            if self.phase is Phase.PLAYING:  # only the restart, not construction
                self.died()

    game = Cursed(services, store)
    to_playing_raw(game)
    game.died()
    game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    assert game.phase is Phase.GAME_OVER and game.transition is None


def to_playing_raw(game) -> None:
    """``to_playing`` without its asserts, for games whose hooks derail the flow."""
    game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)


def test_intro_returns_to_standby_only_after_the_configured_loops(game):
    game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    for _ in range(game.INTRO_LOOPS_BEFORE_STANDBY - 1):
        assert not game.send(Event.INTRO_FINISHED)
    assert game.send(Event.INTRO_FINISHED)
    run_for(game, game.STANDBY_FADE_TIME)
    assert game.phase is Phase.STANDBY
    # The loop count must reset with the phase, not carry into the next visit.
    game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    assert not game.send(Event.INTRO_FINISHED)


def test_game_over_delay_swallows_confirm_until_it_elapses(services, store):
    class Slow(ProbeGame):
        GAME_OVER_DELAY = 1.0

    game = Slow(services, store)
    to_playing(game)
    game.died()
    game.on_action("confirm")
    assert game.transition is None  # a still-mashing player can't skip the death
    run_for(game, 1.0)
    game.on_action("confirm")
    assert game.transition is not None


def test_a_new_run_resets_every_per_run_resource(game):
    to_playing(game)
    game.score, game.elapsed = 99, 12.0
    game.particles.emit((DOT,), 0, 0)
    stars = game.starfield
    game.died()
    game.send(Event.CONFIRM)
    run_for(game, game.GAMEPLAY_FADE_TIME)
    assert (game.score, game.particles.items, game.is_new_high_score) == (0, [], False)
    assert game.elapsed < 1.0
    assert game.starfield is not stars


def test_hundreds_of_runs_do_not_accumulate_state(game):
    to_playing(game)
    for _ in range(200):
        game.particles.emit((DOT,), 0, 0, scale=50)
        game.died()
        game.send(Event.CONFIRM)
        run_for(game, game.GAMEPLAY_FADE_TIME)
    ps = game.particles
    assert len(ps.items) + len(ps._free) <= ps.budget
    assert len(game.starfield.stars) == game.NUM_STARS
    assert game.log.count("reset") == 201


# --- High scores -----------------------------------------------------------------


def test_high_score_survives_a_new_instance(services, store):
    game = ProbeGame(services, store)
    to_playing(game)
    game.score = 1234
    game.died()
    assert ProbeGame(services, store).high_score == 1234


def test_quitting_mid_run_still_records_the_score(services, store):
    game = ProbeGame(services, store)
    to_playing(game)
    game.score = 77
    game.send(Event.PAUSE)
    game.stop()
    assert store.load() == 77


@pytest.mark.parametrize(
    "contents",
    [
        "",
        "{",
        "null",
        "[]",
        '{"high_score": "lots"}',
        '{"high_score": NaN}',
        '{"high_score": Infinity}',
        '{"high_score": -50}',
        '{"wrong_key": 5}',
        "\x00\xff garbage",
    ],
)
def test_corrupt_save_files_read_as_zero(tmp_path, contents):
    path = tmp_path / "hs.json"
    path.write_text(contents, encoding="latin-1")
    assert HighScoreStore(path).load() == 0


def test_save_never_lowers_and_handles_huge_scores(tmp_path):
    store = HighScoreStore(tmp_path / "deep" / "nested" / "hs.json")
    store.save(10**30)
    store.save(5)
    assert store.load() == 10**30
    assert json.loads(store.path.read_text()) == {"high_score": 10**30}
    assert not store.path.with_suffix(".tmp").exists()


def test_unwritable_save_location_does_not_raise(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    HighScoreStore(blocker / "hs.json").save(5)  # parent is a file: logged, not raised


# --- Particle pool -------------------------------------------------------------


@pytest.mark.parametrize("budget", [0, 1, 7, 1500])
def test_particle_budget_is_never_exceeded(budget):
    ps = ParticleSystem(budget)
    rng = random.Random(3)
    for _ in range(300):
        ps.emit((DOT, DOT), 0, 0, scale=rng.choice((0.0, 1.0, 40.0)))
        ps.update(rng.choice((0.0, 1 / 64, 0.4)))
        assert len(ps.items) <= budget
        assert len(ps.items) + len(ps._free) <= budget  # the free list can't leak


def test_lowering_the_budget_at_runtime_drops_new_emits_cleanly():
    ps = ParticleSystem(100)
    ps.emit((DOT,), 0, 0, scale=20)
    ps.budget = 10
    ps.emit((DOT,), 0, 0)
    assert len(ps.items) == 100  # nothing new, nothing negative


@pytest.mark.parametrize("scale", [0.0, -1.0, -1e9, 1e-12, 1e9])
def test_emit_scale_extremes_respect_floor_and_budget(scale):
    ps = ParticleSystem(500)
    effect = ParticleEffect(10, (1.0, 1.0), (WHITE, WHITE), min_count=2)
    ps.emit((effect,), 0, 0, scale=scale)
    assert 2 <= len(ps.items) <= 500


def test_recycled_particles_carry_no_stale_state():
    ps = ParticleSystem(10)
    ps.emit(
        (
            ParticleEffect(
                10, (9.0, 9.0), (WHITE, WHITE), shapes=(Shape.SHARD,), spin=(90, 90)
            ),
        ),
        5,
        5,
        anchor="old",
    )
    ps.clear()
    ps.emit((DOT,), 1, 2)
    assert all(
        p.anchor is None and p.effect is DOT and p.shape is Shape.DOT for p in ps.items
    )
    assert all((p.x, p.y) == (1, 2) and p.life == p.max_life for p in ps.items)


@pytest.mark.parametrize("dt", [math.nan, math.inf])
def test_non_finite_dt_culls_particles_instead_of_poisoning_them(dt):
    ps = ParticleSystem()
    ps.emit((DOT,), 0, 0)
    ps.update(dt)
    assert ps.items == []


@pytest.mark.parametrize("drag", [0.5, 5.0, 30.0])
def test_drag_at_the_fixed_step_slows_without_reversing(drag):
    ps = ParticleSystem()
    ps.emit(
        (ParticleEffect(5, (99.0, 99.0), (WHITE, WHITE), speed=(100, 100), drag=drag),),
        0,
        0,
    )
    signs = [(math.copysign(1, p.vx), math.copysign(1, p.vy)) for p in ps.items]
    for _ in range(640):
        ps.update(1 / 64)
    assert [(math.copysign(1, p.vx), math.copysign(1, p.vy)) for p in ps.items] == signs


def test_drag_never_reverses_even_with_a_long_step():
    ps = ParticleSystem()
    effect = ParticleEffect(
        1, (99.0, 99.0), (WHITE, WHITE), speed=(100, 100), spread=0.0, drag=2.0
    )
    ps.emit((effect,), 0, 0, heading=90)
    vx = ps.items[0].vx
    ps.update(1.0)
    assert ps.items[0].vx * vx >= 0


# --- Starfield --------------------------------------------------------------------


class StarPainter:
    """Records where a starfield draws its stars."""

    def __init__(self):
        self.spots: list[tuple[float, float]] = []

    def setPen(self, pen):
        pass

    def setBrush(self, brush):
        pass

    def drawEllipse(self, rect):
        self.spots.append((rect.x(), rect.y()))


def star_spots(field: StarField, ahead: float) -> list[tuple[float, float]]:
    painter = StarPainter()
    field.draw(painter, 800, 600, ahead)
    return painter.spots


def test_stars_left_unscrolled_stay_still_between_steps(game):
    """The first run follows the intro's drift, and a pause follows play:
    neither may carry its velocity into frames that don't scroll."""
    to_playing(game)  # ProbeGame never scrolls during play
    run_for(game, game.dt)
    assert star_spots(game.starfield, 0) == star_spots(game.starfield, game.dt)
    game.starfield.scroll(0, -480, game.dt)
    assert game.send(Event.PAUSE)
    run_for(game, game.dt)
    assert star_spots(game.starfield, 0) == star_spots(game.starfield, game.dt)


def test_engine_effects_leave_the_global_random_alone(game):
    """Stars and particles draw from their own rng, so however many explosions
    a run shows, the numbers its gameplay draws stay the same."""
    random.seed(99)
    before = random.getstate()
    to_playing(game)
    game.particles.emit((DOT, DOT), 0, 0, scale=40.0)
    assert game.particles.items
    run_for(game, 0.5)
    game.died()
    game.send(Event.CONFIRM)  # a fresh run rebuilds the starfield
    run_for(game, game.GAMEPLAY_FADE_TIME * 2)
    assert random.getstate() == before


@pytest.mark.parametrize(
    "velocity", [(0, -480), (1e12, -1e12), (-1e-300, 0), (0, 1e300)]
)
def test_starfield_wraps_inside_the_canvas_for_any_finite_velocity(velocity):
    field = StarField(800, 600, 100)
    for _ in range(100):
        field.scroll(*velocity, 1 / 64)
    # <=, not <: Python's float modulo can round a tiny negative up to the modulus.
    assert all(0 <= s.x <= 800 and 0 <= s.y <= 600 for s in field.stars)


# --- Host: theme ----------------------------------------------------------------


def test_the_theme_takes_each_apps_accent_and_keeps_it_if_the_next_fails(host):
    def tinted(accent: str, create=FakeApp) -> GameDefinition:
        return GameDefinition(
            GameInfo(f"tint-{accent[1:]}", "T", "qade_engine", accent=accent), create
        )  # type: ignore[arg-type]

    host.switch_to(tinted("#80de54"))
    green = oklch(current_theme().accent)[2]
    host.switch_to(tinted("#9678ff"))
    purple = oklch(current_theme().accent)[2]
    assert green == pytest.approx(oklch(QColor("#80de54"))[2], abs=2)
    assert purple == pytest.approx(oklch(QColor("#9678ff"))[2], abs=2)

    def broken(services):
        raise RuntimeError("no")

    with pytest.raises(RuntimeError):
        host.switch_to(tinted("#ff0000", broken))
    assert oklch(current_theme().accent)[2] == purple
