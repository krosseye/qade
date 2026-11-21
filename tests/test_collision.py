# SPDX-License-Identifier: GPL-3.0-or-later
"""Spatial logic: overlap boundaries, tunneling, projection and numeric abuse."""

import math

import pytest
from PySide6.QtCore import QRectF
from support import NASTY_FLOATS, define, to_playing

from examples.dodge.game import BLOCK_SIZE, BLOCK_SPEED, PLAYER_WIDTH, Action, Dodge
from qade_engine import Phase
from qade_engine.core import PlayField, clamp, dist_sq, lerp
from qade_engine.graphics.camera import NEAR, Camera, Pose


@pytest.mark.parametrize("value", [*NASTY_FLOATS, 0.0, 0.5, 1.0, -1.0, 2.0])
def test_clamp_always_lands_in_range_even_for_non_finite_input(value):
    """NaN must not escape clamp, or it poisons every position it touches."""
    result = clamp(value, 0.0, 1.0)
    assert 0.0 <= result <= 1.0


def test_clamp_nan_falls_to_the_low_bound():
    """Documented so a refactor (e.g. to min(max())) can't silently change it."""
    assert clamp(math.nan, -3.0, 7.0) == -3.0


def test_clamp_inverted_bounds_returns_low():
    """A field narrower than the player (low > high) pins to the left edge."""
    assert clamp(50.0, 30.0, 10.0) == 30.0


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ((0, 0), (0, 0)),
        ((1e-200, 0), (0, 0)),  # underflows to 0
        ((-1e308, 0), (1e308, 0)),  # overflows to inf, never NaN
        ((3, 4), (0, 0)),
        ((-5, -5), (5, 5)),
    ],
)
def test_dist_sq_is_symmetric_and_non_negative(a, b):
    d1, d2 = dist_sq(*a, *b), dist_sq(*b, *a)
    assert d1 == d2 and d1 >= 0 and not math.isnan(d1)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_positions_never_register_a_hit(bad):
    radius_sq = 10.0**2
    d = dist_sq(bad, 0.0, 0.0, 0.0)
    # Phrased as a game's hit check; `d >= radius_sq` would wrongly fail for NaN.
    assert not d < radius_sq


def test_lerp_hits_its_endpoints():
    assert lerp(-7.25, 1e9, 0.0) == -7.25
    assert lerp(-7.25, 1e9, 1.0) == pytest.approx(1e9)
    assert lerp(3.0, 3.0, 1e300) == 3.0  # a zero-length range ignores amount


# --- Dodge: overlap boundaries and tunneling -------------------------------


@pytest.fixture
def dodge(services, store):
    game = Dodge(services, high_score_store=store)
    to_playing(game)
    game.spawn_timer = math.inf  # tests place every block by hand
    game.blocks.clear()
    yield game
    game.stop()


def block_above_player(game: Dodge, gap: float) -> QRectF:
    player = game.player_rect()
    left = player.center().x() - BLOCK_SIZE / 2
    return QRectF(left, player.top() - BLOCK_SIZE - gap, BLOCK_SIZE, BLOCK_SIZE)


@pytest.mark.parametrize(
    ("gap", "dies"),
    [
        (1.0, False),
        (0.0, False),  # edges touching is not a hit
        (-1e-6, True),  # the thinnest overlap is
        (-BLOCK_SIZE, True),
    ],
)
def test_overlap_boundary_is_strict(dodge, gap, dies):
    dodge.drop_block(block_above_player(dodge, gap))
    dodge.step_playing(0.0)
    assert (dodge.phase is Phase.GAME_OVER) is dies


def test_zero_size_hazard_never_collides(dodge):
    centre = dodge.player_rect().center()
    dodge.drop_block(QRectF(centre.x(), centre.y(), 0.0, 0.0))
    dodge.step_playing(0.0)
    assert dodge.phase is Phase.PLAYING


@pytest.mark.parametrize("frame_time", [1 / 240, 1 / 60, 1 / 15, 0.25, 3.0])
def test_fixed_steps_prevent_tunneling_through_the_player(
    host, clock, store, frame_time
):
    """However long frames take, the host's fixed steps catch the block mid-player."""
    games: list[Dodge] = []
    host.switch_to(
        define(lambda s: games.append(Dodge(s, store)) or games[-1], "dodge")
    )
    game = games[0]
    to_playing(game)
    game.spawn_timer = math.inf
    game.drop_block(block_above_player(game, gap=1.0))
    for _ in range(200):
        clock.advance(frame_time)
        host.tick()
        if game.phase is Phase.GAME_OVER:
            break
    assert game.phase is Phase.GAME_OVER


def test_a_single_variable_step_would_tunnel(dodge):
    """Proves the fixed step is load-bearing: one 0.25 s step jumps clean over the player."""
    assert BLOCK_SPEED * 0.25 > BLOCK_SIZE + dodge.player_rect().height()
    dodge.drop_block(block_above_player(dodge, gap=1.0))
    dodge.step_playing(0.25)
    assert dodge.phase is Phase.PLAYING
    assert dodge.blocks[0].value.top() > dodge.player_rect().bottom()


def test_conflicting_steering_nets_zero(dodge):
    dodge.actions.apply({Action.LEFT: 1.0, Action.RIGHT: 1.0})
    x = dodge.player_x.value
    for _ in range(64):
        dodge.step(dodge.dt)
    assert dodge.player_x.value == x


@pytest.mark.parametrize("direction", [Action.LEFT, Action.RIGHT])
@pytest.mark.parametrize("dt", [1 / 64, 10.0, 1e12, math.inf])
def test_player_never_leaves_the_field(dodge, direction, dt):
    dodge.actions.apply({direction: 1.0})
    dodge.step_playing(dt)
    half = PLAYER_WIDTH / 2
    assert half <= dodge.player_x.value <= dodge.field.width - half


@pytest.mark.parametrize("poison", [math.nan, math.inf, -math.inf])
def test_player_recovers_from_a_poisoned_position(dodge, poison):
    """clamp() snaps a NaN/inf position back into the field instead of spreading it."""
    dodge.player_x.jump(poison)
    dodge.step_playing(1 / 64)
    assert math.isfinite(dodge.player_x.value)


def test_each_dodged_block_scores_exactly_once(dodge):
    far_left = QRectF(0, dodge.field.height - 1, BLOCK_SIZE, BLOCK_SIZE)
    dodge.player_x.jump(dodge.field.width - PLAYER_WIDTH)  # out of the way
    dodge.drop_block(QRectF(far_left))
    dodge.drop_block(QRectF(far_left))
    for _ in range(64):
        dodge.step_playing(1 / 64)
    assert dodge.score == 2 and dodge.blocks == []


def test_many_blocks_in_one_step_mutate_safely(dodge):
    """Culling from the list mid-iteration must not skip or double-count a block."""
    dodge.player_x.jump(dodge.field.width - PLAYER_WIDTH / 2)
    for i in range(5000):
        dodge.drop_block(QRectF(0, dodge.field.height - 0.5 - i % 3, 1, 1))
    dodge.step_playing(1 / 64)
    assert dodge.score + len(dodge.blocks) == 5000


# --- PlayField ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("w", "h"), [(800, 600), (1600, 600), (800, 6000), (0.001, 600)]
)
def test_play_field_scales_relative_to_its_canvas(w, h):
    field = PlayField(800, 600)
    assert field.area_scale == 1.0
    field.width, field.height = w, h
    assert field.width_scale == pytest.approx(w / 800)
    assert field.area_scale == pytest.approx(w * h / (800 * 600))


# --- Camera ------------------------------------------------------------------


def camera(yaw: float = 0.0, **pose) -> Camera:
    return Camera(
        Pose(pose.get("x", 0.0), pose.get("y", 0.0), pose.get("z", 0.0), yaw),
        500,
        400,
        300,
    )


def test_straight_ahead_projects_to_the_centre():
    point = camera().project((0.0, 0.0, 10.0))
    assert point is not None and (point.x(), point.y()) == (400, 300)


@pytest.mark.parametrize("yaw", [0.0, 37.5, -90.0, 180.0, 359.999, 1e6, -1e9])
def test_camera_rotation_preserves_distances(yaw):
    """Turning must be a pure rotation: no drift or scaling at any heading."""
    cam = camera(yaw, x=3.0, z=-2.0)
    for point in [(10.0, 0.0, 5.0), (-4.0, 2.0, -9.0), (0.0, -1.0, 1e5)]:
        vx, vy, vz = cam.to_view(point)
        dx, dz = point[0] - 3.0, point[2] + 2.0
        assert math.hypot(vx, vz) == pytest.approx(math.hypot(dx, dz), rel=1e-9)
        assert vy == point[1]


@pytest.mark.parametrize("turns", [1, 2, 10, 1000])
def test_full_turns_return_to_the_same_view(turns):
    a = camera(0.0).project((5.0, 1.0, 20.0))
    b = camera(360.0 * turns).project((5.0, 1.0, 20.0))
    assert a is not None and b is not None
    assert (b.x(), b.y()) == pytest.approx((a.x(), a.y()), abs=1e-6)


@pytest.mark.parametrize(
    ("z", "visible"),
    [(NEAR, True), (NEAR * 0.999999, False), (0.0, False), (-5.0, False)],
)
def test_near_plane_boundary(z, visible):
    assert (camera().project((0.0, 0.0, z)) is not None) is visible


def test_point_behind_after_a_half_turn():
    assert camera(180.0).project((0.0, 0.0, 10.0)) is None


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_projecting_non_finite_points_fails_gracefully(bad):
    cam = camera()
    for point in [(bad, 0.0, 10.0), (0.0, bad, 10.0), (0.0, 0.0, bad)]:
        cam.project(point)  # must not raise
        cam.line(point, (0.0, 0.0, 5.0))
        cam.polygon([point, (1.0, 0.0, 5.0), (0.0, 1.0, 5.0)])


def test_line_wholly_behind_is_culled():
    assert camera().line((0.0, 0.0, -1.0), (5.0, 5.0, -10.0)) is None


@pytest.mark.parametrize("behind", [-1.0, -1e6, 0.0, NEAR * 0.5])
def test_line_through_the_viewer_is_clipped_to_finite_coords(behind):
    """Guards against smearing: a segment crossing the near plane is cut, not projected raw."""
    line = camera().line((1.0, 1.0, behind), (1.0, 1.0, 10.0))
    assert line is not None
    for p in (line.p1(), line.p2()):
        assert math.isfinite(p.x()) and math.isfinite(p.y())
        # x=1 cut at the near plane projects to focal * 1 / NEAR from centre, at most.
        assert abs(p.x() - 400) <= 500 * 1.0 / NEAR + 1e-6


def test_edge_on_line_at_the_near_plane_does_not_divide_by_zero():
    line = camera().line((0.0, 0.0, NEAR), (5.0, 0.0, NEAR))
    assert line is not None


@pytest.mark.parametrize(
    ("depths", "corners"),
    [
        ((5, 5, 5, 5), 4),  # wholly in front: untouched
        ((-5, -5, -5, -5), None),  # wholly behind: culled
        ((5, 5, -5, -5), 4),  # half behind: two corners replaced by two cuts
        ((5, -5, -5, -5), 3),  # one corner in front: a triangle
        ((5, 5, 5, -5), 5),  # one corner behind: a pentagon
    ],
)
def test_polygon_near_plane_clipping(depths, corners):
    square = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
    points = [(x, y, float(z)) for (x, y), z in zip(square, depths, strict=True)]
    polygon = camera().polygon(points)
    if corners is None:
        assert polygon is None
    else:
        assert polygon is not None and polygon.count() == corners
        assert all(math.isfinite(p.x()) and math.isfinite(p.y()) for p in polygon)


def test_degenerate_polygons_are_culled():
    cam = camera()
    assert cam.polygon([]) is None
    assert cam.polygon([(0.0, 0.0, 5.0), (1.0, 0.0, 5.0)]) is None


@pytest.mark.parametrize("amount", [0.0, 1.0])
def test_pose_lerp_hits_endpoints(amount):
    a, b = Pose(0, 0, 0, 0), Pose(10, -5, 3, 270)
    assert a.lerp(b, amount) == (a if amount == 0.0 else b)


def test_the_paddle_draws_between_its_last_two_steps(dodge):
    dodge.actions.apply({Action.RIGHT: 1.0})
    before = dodge.player_x.value
    dodge.step(dodge.dt)
    after = dodge.player_x.value
    assert after > before
    assert (dodge.player_x.at(0.0), dodge.player_x.at(1.0)) == (before, after)
    dodge.actions.apply({})
    dodge.step(dodge.dt)
    assert dodge.player_x.at(0.0) == dodge.player_x.at(1.0) == after
