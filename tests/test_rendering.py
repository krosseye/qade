# SPDX-License-Identifier: GPL-3.0-or-later
"""Rendering: canvas mapping, clearing, painter-state hygiene and offscreen pixels."""

import math
from collections.abc import Callable

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from support import (
    FakeApp,
    ProbeGame,
    blank_image,
    define,
    painter_geometry,
    painter_style,
    to_playing,
)

from qade_engine import Event, Phase
from qade_engine.core.state_machine import Transition, TransitionStyle
from qade_engine.graphics import WHITE, Viewport
from qade_engine.graphics.particles import ParticleEffect, ParticleSystem, Shape
from qade_engine.graphics.primitives import draw_centered, draw_corner_brackets
from qade_engine.graphics.starfield import StarField
from qade_engine.graphics.transitions import draw_transition
from qade_engine.host.app import Frame
from qade_engine.host.view import RasterView
from qade_engine.narration import IntroSequencer
from qade_engine.perf import PerfStats
from qade_engine.ui import HudRow, draw_hud_panel, draw_terminal_frame
from qade_engine.ui.hud import draw_game_over, draw_hud, draw_paused
from qade_engine.ui.overlays import draw_intro, draw_standby

CANVAS = (800, 600)
BLACK_RGB = QColor(0, 0, 0).rgb()
WHITE_RGB = QColor(255, 255, 255).rgb()

EXTREME_WINDOWS = [
    (800, 600),
    (1600, 1200),
    (1920, 600),  # ultra-wide
    (800, 2400),  # ultra-tall
    (4000, 120),
    (120, 4000),
    (801, 599),  # off-by-one aspect
    (7, 5),
]


def rgb(image: QImage, x: float, y: float) -> int:
    return image.pixelColor(int(x), int(y)).rgb()


# --- Viewport ----------------------------------------------------------------


@pytest.mark.parametrize("window", EXTREME_WINDOWS + [(3840, 2160), (1, 10_000)])
def test_viewport_fit_covers_the_window_and_contains_the_canvas(window):
    view = Viewport.fit(window, CANVAS)
    assert view.width * view.scale == pytest.approx(window[0])
    assert view.height * view.scale == pytest.approx(window[1])
    if view.scale > 0.1:  # above the floor the whole canvas always fits
        assert view.width >= CANVAS[0] - 1e-9 and view.height >= CANVAS[1] - 1e-9
        assert min(view.width - CANVAS[0], view.height - CANVAS[1]) == pytest.approx(
            0, abs=1e-9
        )


@pytest.mark.parametrize("window", [(0, 0), (0, 600), (800, 0), (1, 1)])
def test_viewport_fit_degenerate_windows_never_divide_by_zero(window):
    view = Viewport.fit(window, CANVAS)
    assert view.scale == pytest.approx(0.1) or view.scale > 0
    assert math.isfinite(view.width) and math.isfinite(view.height)


# --- Host paint: mapping and clearing -----------------------------------------


@pytest.fixture
def canvas_app(host):
    """A running app that fills its whole canvas white."""
    apps: list[FakeApp] = []

    def create(services):
        app = FakeApp(services)
        app.on_draw = lambda f: f.painter.fillRect(QRectF(0, 0, *CANVAS), WHITE)
        apps.append(app)
        return app

    host.switch_to(define(create))
    return host, apps[0]


def paint(host, size) -> QImage:
    image = blank_image(*size)
    painter = QPainter(image)
    host.paint(painter, size)
    painter.end()
    return image


@pytest.mark.parametrize("window", [w for w in EXTREME_WINDOWS if min(w) >= 100])
def test_canvas_maps_to_the_expected_pixels_at_any_aspect(canvas_app, window):
    """The canvas is scaled uniformly and anchored top-left; the rest is black."""
    host, _ = canvas_app
    image = paint(host, window)
    scale = Viewport.fit(window, CANVAS).scale
    right, bottom = CANVAS[0] * scale, CANVAS[1] * scale
    assert rgb(image, 1, 1) == WHITE_RGB
    assert rgb(image, right - 2, bottom - 2) == WHITE_RGB
    if right + 2 < window[0]:
        assert rgb(image, right + 2, 1) == BLACK_RGB
    if bottom + 2 < window[1]:
        assert rgb(image, 1, bottom + 2) == BLACK_RGB


@pytest.mark.parametrize("window", EXTREME_WINDOWS)
def test_paint_hands_the_app_a_uniform_unrotated_scale(canvas_app, window):
    """Guards against stretched vectors: x and y scale must match, with no shear."""
    host, app = canvas_app
    seen = []
    app.on_draw = lambda f: seen.append((f.painter.transform(), f.view))
    paint(host, window)
    transform, view = seen[0]
    assert (
        transform.m11() == pytest.approx(transform.m22()) == pytest.approx(view.scale)
    )
    assert transform.m12() == transform.m21() == 0.0
    assert (transform.dx(), transform.dy()) == (0.0, 0.0)


def test_paint_with_no_app_clears_everything(host):
    image = paint(host, (64, 48))
    expected = blank_image(64, 48, QColor(0, 0, 0))
    assert image == expected


def test_paint_clears_before_drawing_even_when_the_app_draws_nothing(host):
    host.switch_to(define(FakeApp))
    assert paint(host, (64, 48)) == blank_image(64, 48, QColor(0, 0, 0))


def test_frames_are_isolated_through_the_real_view(canvas_app):
    """A frame that trashes painter state must not affect the next frame."""
    host, app = canvas_app
    view = RasterView(host)
    view.resize(400, 300)

    def poison(frame: Frame) -> None:
        p = frame.painter
        p.setOpacity(0.0)
        p.rotate(45)
        p.setClipRect(QRectF(0, 0, 1, 1))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        # Only the first frame poisons; the second must still come out white.
        app.on_draw = lambda f: f.painter.fillRect(QRectF(0, 0, *CANVAS), WHITE)

    app.on_draw = poison
    view.grab()
    image = view.grab().toImage()
    assert rgb(image, 1, 1) == WHITE_RGB
    assert rgb(image, 398, 298) == WHITE_RGB
    view.deleteLater()


# --- Painter state hygiene ------------------------------------------------------


def hostile_painter(image: QImage) -> QPainter:
    """A painter already carrying every kind of state a helper could clobber."""
    p = QPainter(image)
    p.translate(13, 7)
    p.rotate(17)
    p.scale(0.5, 2.0)  # non-uniform, to catch helpers that reset the transform
    p.setOpacity(0.6)
    p.setClipRect(QRectF(5, 5, 300, 200))
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return p


VIEW = Viewport(800, 600, 1.0)
ROWS = [HudRow("SCORE", "000123", WHITE), HudRow("", "", WHITE)]


def _particles() -> ParticleSystem:
    ps = ParticleSystem()
    effect = ParticleEffect(
        12, (0.5, 1.0), (WHITE, WHITE), shapes=tuple(Shape), speed=(10, 90), size=(1, 8)
    )
    ps.emit((effect,), 10, 10, anchor="a")
    ps.emit((effect,), 50, 50)
    ps.emit((effect,), 0, 0, anchor="b")
    ps.emit((effect,), 0, 0, anchor="a")
    return ps


def _intro() -> IntroSequencer:
    intro = IntroSequencer(["ONE", "TWO", "THREE"], use_tts=False)
    intro.start()
    return intro


SCREEN_HELPERS: dict[str, Callable[[QPainter], None]] = {
    "standby": lambda p: draw_standby(p, VIEW, 12.3, "T", "MSG", "PROMPT"),
    "intro": lambda p: draw_intro(p, VIEW, _intro(), 99.0, "T", "PROMPT", ("TWO",)),
    "paused": lambda p: draw_paused(p, VIEW, "PAUSED", "P"),
    "game_over_new_best": lambda p: draw_game_over(
        p, VIEW, "OVER", "AGAIN", 5, 5, True
    ),
    "game_over": lambda p: draw_game_over(
        p, VIEW, "OVER", "AGAIN", 999_999_999, 0, False
    ),
    "game_over_float_score": lambda p: draw_game_over(
        p, VIEW, "OVER", "AGAIN", 12.7, 3.5, False
    ),
    "hud": lambda p: draw_hud(p, VIEW, ROWS, PerfStats(show_details=True)),
    "hud_no_rows": lambda p: draw_hud(p, VIEW, [], PerfStats()),
    "hud_panel": lambda p: draw_hud_panel(p, 0, 0, 200, "SYS", ROWS),
}

LEAF_HELPERS: dict[str, Callable[[QPainter], None]] = {
    "terminal_frame": lambda p: draw_terminal_frame(p, 0, 0, 300, 100, "TITLE"),
    "brackets": lambda p: draw_corner_brackets(p, 0, 0, -50, -50, 10, WHITE),
    "centered_text": lambda p: draw_centered(p, "x" * 500, 100, 50),
    "starfield": lambda p: StarField(800, 600, 50).draw(p, 1920, 200, ahead=0.5),
    "particles_mixed_anchors": lambda p: _particles().draw(
        p, ahead=0.01, place=lambda a: None if a == "b" else (100, 100, 3.0)
    ),
    "particles_no_placer": lambda p: _particles().draw(p),
    **{
        f"fade_{progress}": (
            lambda p, progress=progress: draw_transition(
                p,
                800,
                600,
                Transition(
                    Phase.STANDBY, Phase.INTRO, TransitionStyle.FADE, 1.0, progress
                ),
            )
        )
        for progress in (0.0, 0.5, 1.0, 7.0)
    },
}


@pytest.mark.parametrize("helper", SCREEN_HELPERS, ids=str)
def test_screen_helpers_restore_all_painter_state(helper):
    """Screen-level draws save/restore everything, so the caller's pen and font survive."""
    image = blank_image(320, 240)
    p = hostile_painter(image)
    before = painter_geometry(p), painter_style(p)
    SCREEN_HELPERS[helper](p)
    assert (painter_geometry(p), painter_style(p)) == before
    p.end()


@pytest.mark.parametrize("helper", LEAF_HELPERS, ids=str)
def test_leaf_helpers_never_leak_transform_clip_or_opacity(helper):
    """Leaf draws may set pen/brush, but geometry leaks would skew every later draw."""
    image = blank_image(320, 240)
    p = hostile_painter(image)
    before = painter_geometry(p)
    LEAF_HELPERS[helper](p)
    assert painter_geometry(p) == before
    p.end()


@pytest.mark.parametrize(
    "phase_path", ["standby", "intro", "playing", "paused", "game_over", "fading"]
)
@pytest.mark.parametrize("alpha", [0.0, 0.999, 1.0])
def test_arcade_draw_is_pure_and_leak_free(game, phase_path, alpha):
    """``draw`` reads state and never modifies it, in every phase, at any alpha."""
    game.start()
    if phase_path != "standby":
        game.send(Event.CONFIRM)
        if phase_path == "fading":
            for _ in range(5):
                game.step(game.dt)
        else:
            for _ in range(game.tick_hz):
                game.step(game.dt)
    if phase_path in ("playing", "paused", "game_over"):
        to_playing_from_intro(game)
        game.score = 42
        effect = ParticleEffect(30, (1.0, 2.0), (WHITE, WHITE), speed=(10, 50))
        game.particles.emit((effect,), 100, 100)
    if phase_path == "paused":
        game.send(Event.PAUSE)
    if phase_path == "game_over":
        game.died()

    snapshot = _game_snapshot(game)
    image = blank_image(400, 300)
    p = hostile_painter(image)
    before = painter_geometry(p)
    game.draw(Frame(p, Viewport(800, 600, 1.0), now=5.0, alpha=alpha, perf=PerfStats()))
    assert painter_geometry(p) == before
    p.end()
    assert _game_snapshot(game) == snapshot


def to_playing_from_intro(game) -> None:
    game.send(Event.CONFIRM)
    for _ in range(game.tick_hz):
        game.step(game.dt)
    assert game.phase is Phase.PLAYING


def _game_snapshot(game) -> tuple:
    return (
        game.phase,
        game.score,
        game.elapsed,
        game.tick_count,
        game.transition and game.transition.elapsed,
        [(s.x, s.y) for s in game.starfield.stars],
        [(q.x, q.y, q.vx, q.vy, q.life) for q in game.particles.items],
    )


@pytest.mark.parametrize(
    "transform",
    [
        lambda p: p.scale(1e-6, 1e-6),
        lambda p: p.scale(1e6, 1e6),
        lambda p: p.scale(-1, 1),  # mirrored
        lambda p: p.scale(40, 0.01),  # absurdly non-uniform
        lambda p: p.rotate(90),
        lambda p: p.rotate(-359.999),
        lambda p: p.translate(-1e9, 1e9),
    ],
    ids=[
        "micro",
        "mega",
        "mirror",
        "squash",
        "rot90",
        "rot-almost-360",
        "far-translate",
    ],
)
def test_full_frame_survives_extreme_transforms(game, transform):
    game.start()
    to_playing(game)
    image = blank_image(200, 150)
    p = QPainter(image)
    transform(p)
    before = painter_geometry(p)
    game.draw(Frame(p, Viewport(800, 600, 1.0), now=0.0, alpha=0.5, perf=PerfStats()))
    assert painter_geometry(p) == before
    p.end()


# --- Offscreen pixel checks for effects ----------------------------------------


@pytest.mark.parametrize(
    ("progress", "expected_darkness"),
    [(0.0, 0.0), (0.25, 0.5), (0.5, 1.0), (0.75, 0.5), (1.0, 0.0), (3.0, 0.0)],
)
def test_fade_darkness_is_a_symmetric_tent(progress, expected_darkness):
    """Fully black at the switch, invisible at both ends, and clamped past the end."""
    image = blank_image(20, 20, QColor(255, 255, 255))
    p = QPainter(image)
    transition = Transition(
        Phase.STANDBY, Phase.INTRO, TransitionStyle.FADE, 2.0, progress * 2.0
    )
    draw_transition(p, 20, 20, transition)
    p.end()
    assert image.pixelColor(10, 10).red() == pytest.approx(
        255 * (1 - expected_darkness), abs=2
    )


def test_anchored_particles_draw_where_placed_and_hidden_ones_draw_nothing():
    effect = ParticleEffect(1, (1.0, 1.0), (WHITE, WHITE), size=(10.0, 10.0))
    ps = ParticleSystem()
    ps.emit((effect,), 0, 0, anchor="shown")
    ps.emit((effect,), 0, 0, anchor="hidden")

    image = blank_image(200, 200, QColor(0, 0, 0))
    p = QPainter(image)
    ps.draw(p, place=lambda a: (150.0, 40.0, 2.0) if a == "shown" else None)
    p.end()

    assert rgb(image, 150, 40) == WHITE_RGB
    assert rgb(image, 150 + 8, 40) == WHITE_RGB  # scaled x2: radius 10
    assert rgb(image, 150 + 14, 40) == BLACK_RGB
    assert rgb(image, 0, 0) == BLACK_RGB  # the hidden anchor drew nothing at its offset


def test_particles_with_non_finite_geometry_do_not_crash_the_painter():
    ps = ParticleSystem()
    effect = ParticleEffect(
        20, (1.0, 1.0), (WHITE, WHITE), shapes=tuple(Shape), speed=(1e308, 1e308)
    )
    ps.emit((effect,), 0, 0)
    ps.items[0].x = math.nan
    ps.items[1].y = math.inf
    ps.items[2].size = -5.0
    ps.update(1.0 / 64)  # huge speeds fling the rest far off-canvas
    image = blank_image(50, 50)
    p = QPainter(image)
    ps.draw(p, ahead=1.0)
    p.end()


def test_zero_life_particles_can_be_drawn_before_their_first_update():
    """A 0 s life makes ``max_life`` zero, and ``draw`` divides by it."""
    ps = ParticleSystem()
    ps.emit((ParticleEffect(3, (0.0, 0.0), (WHITE, WHITE)),), 10, 10)
    image = blank_image(20, 20)
    p = QPainter(image)
    try:
        ps.draw(p)
    finally:
        p.end()


def test_starfield_spreads_over_any_view_size():
    field = StarField(800, 600, 300)
    for view in [(800, 600), (5000, 100), (100, 5000), (1, 1)]:
        hits: list[tuple[float, float]] = []

        # Duck-typed painter: StarField.draw only makes these three calls.
        class Recorder:
            def setPen(self, *_):
                pass

            def setBrush(self, *_):
                pass

            def drawEllipse(self, rect, hits=hits):
                hits.append((rect.center().x(), rect.center().y()))

        field.draw(Recorder(), *view)
        assert len(hits) == 300
        assert all(-1 <= x <= view[0] + 5 and -1 <= y <= view[1] + 5 for x, y in hits)


def test_fill_window_game_grows_its_field_via_a_real_resize(host, store):
    """Resize the real view mid-run: the field follows on the next step."""

    class Wide(ProbeGame):
        FILL_WINDOW = True

    games: list[Wide] = []

    def create(services):
        games.append(Wide(services, store))
        return games[-1]

    host.switch_to(define(create, "wide"))
    game = games[0]
    view = RasterView(host)
    view.resize(800, 600)
    view.grab()
    to_playing(game)
    game.log.clear()
    view.resize(1600, 600)
    view.grab()  # delivers the resize, then ticks and paints
    game.step(game.dt)
    assert game.field.width == pytest.approx(
        1600
    ) and game.field.height == pytest.approx(600)
    assert game.log == [("resized", pytest.approx(800), 0.0)]
    assert game.field.area_scale == pytest.approx(2.0)
    view.deleteLater()


def test_paint_is_skipped_for_an_app_that_already_failed(canvas_app):
    host, app = canvas_app
    app.fail_in = "draw"
    paint(host, (100, 100))
    image = paint(host, (100, 100))
    assert app.calls.count("draw") == 1
    assert rgb(image, 50, 50) == BLACK_RGB  # still cleared: no stale frame
