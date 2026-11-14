# SPDX-License-Identifier: GPL-3.0-or-later
"""Input: Qt key events into actions, chords, focus loss and gamepad edges."""

import math

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from support import FakeApp, ProbeGame, define, to_playing

from qade_engine import Phase
from qade_engine.input import (
    InputMap,
    Key,
    PadAxis,
    PadButton,
    UIAction,
    add_steering,
    add_ui_actions,
)
from qade_engine.input.bindings import DeviceState
from qade_engine.input.gamepad import GamepadAxis, GamepadButton, GamepadState
from qade_engine.input.manager import InputManager
from qade_engine.input.state import ActionState

LEFT_KEYS = (Qt.Key.Key_Left, Qt.Key.Key_A)
RIGHT_KEYS = (Qt.Key.Key_Right, Qt.Key.Key_D)


def steering_map() -> InputMap:
    m = InputMap()
    add_steering(m, "left", "right", LEFT_KEYS, RIGHT_KEYS)
    return add_ui_actions(m, never_confirm=(*LEFT_KEYS, *RIGHT_KEYS))


class ScriptedPad:
    """A gamepad backend that reports whatever ``state`` a test sets and counts closes."""

    def __init__(self) -> None:
        self.state = GamepadState()
        self.closed = 0

    def poll(self) -> GamepadState:
        return self.state

    def close(self) -> None:
        self.closed += 1


@pytest.fixture
def pad() -> ScriptedPad:
    return ScriptedPad()


@pytest.fixture
def rig(pad):
    """A focusable widget whose key events feed an InputManager, plus the presses it emits."""
    manager = InputManager(steering_map(), gamepad_backend=pad)
    widget = QWidget()
    widget.installEventFilter(manager)
    presses: list[str] = []
    manager.action_pressed.connect(presses.append)
    yield manager, widget, presses
    widget.removeEventFilter(manager)
    widget.deleteLater()


def key(widget, kind, k, autorepeat=False) -> bool:
    event = QKeyEvent(kind, k, Qt.KeyboardModifier.NoModifier, "", autorepeat)
    QApplication.sendEvent(widget, event)
    return event.isAccepted()


def press(widget, k, **kw):
    return key(widget, QEvent.Type.KeyPress, k, **kw)


def release(widget, k, **kw):
    return key(widget, QEvent.Type.KeyRelease, k, **kw)


def focus_out(widget):
    QApplication.sendEvent(
        widget,
        QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.ActiveWindowFocusReason),
    )


# --- Event translation ------------------------------------------------------


def test_key_press_and_release_drive_held_state(rig):
    manager, widget, presses = rig
    press(widget, Qt.Key.Key_Left)
    assert manager.state.is_pressed("left") and presses == ["left"]
    release(widget, Qt.Key.Key_Left)
    assert not manager.state.is_pressed("left")
    assert manager.state.was_pressed("left")


def test_autorepeat_never_re_fires_a_press(rig):
    """Guards against OS key repeat firing a one-shot action many times."""
    manager, widget, presses = rig
    press(widget, Qt.Key.Key_P)
    for _ in range(50):
        press(widget, Qt.Key.Key_P, autorepeat=True)
        release(widget, Qt.Key.Key_P, autorepeat=True)
    assert presses.count(UIAction.PAUSE) == 1
    assert manager.state.is_pressed(UIAction.PAUSE)


def test_release_without_press_and_double_press_are_harmless(rig):
    manager, widget, presses = rig
    release(widget, Qt.Key.Key_Right)
    assert not manager.state.is_pressed("right")
    press(widget, Qt.Key.Key_Right)
    press(widget, Qt.Key.Key_Right)
    assert presses.count("right") == 1
    release(widget, Qt.Key.Key_Right)
    assert not manager.state.is_pressed("right")


def test_two_keys_on_one_action_hold_until_both_release(rig):
    manager, widget, presses = rig
    press(widget, Qt.Key.Key_Left)
    press(widget, Qt.Key.Key_A)
    release(widget, Qt.Key.Key_Left)
    assert manager.state.is_pressed("left")
    release(widget, Qt.Key.Key_A)
    assert not manager.state.is_pressed("left")
    assert presses.count("left") == 1


def test_conflicting_directions_are_both_reported(rig):
    """The map reports raw intent; resolving left+right is the game's job (Dodge nets 0)."""
    manager, widget, _ = rig
    press(widget, Qt.Key.Key_Left)
    press(widget, Qt.Key.Key_Right)
    assert manager.state.is_pressed("left") and manager.state.is_pressed("right")


def test_rapid_chord_roll_over(rig):
    manager, widget, presses = rig
    press(widget, Qt.Key.Key_A)
    press(widget, Qt.Key.Key_D)
    release(widget, Qt.Key.Key_A)
    assert (manager.state.is_pressed("left"), manager.state.is_pressed("right")) == (
        False,
        True,
    )
    assert presses == ["left", "right"]


def test_key_events_are_consumed_but_mouse_events_pass(rig):
    manager, widget, _ = rig
    seen: list[int] = []
    widget.keyPressEvent = lambda e: seen.append(e.key())  # type: ignore[method-assign]
    press(widget, Qt.Key.Key_Space)
    assert seen == []
    mouse = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        QPointF(5, 5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    before = dict(manager.state._strengths)
    assert manager.eventFilter(widget, mouse) is False
    assert manager.state._strengths == before


@pytest.mark.parametrize(
    "k",
    [
        Qt.Key.Key_Escape,
        Qt.Key.Key_F3,
        Qt.Key.Key_P,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Meta,
        *LEFT_KEYS,
        *RIGHT_KEYS,
    ],
)
def test_reserved_and_steering_keys_never_confirm(rig, k):
    """Guards against quitting, pausing or still-steering skipping a 'press any key' screen."""
    _, widget, presses = rig
    press(widget, k)
    assert UIAction.CONFIRM not in presses


@pytest.mark.parametrize(
    "k", [Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Z, Qt.Key.Key_F12]
)
def test_ordinary_keys_confirm(rig, k):
    _, widget, presses = rig
    press(widget, k)
    assert UIAction.CONFIRM in presses


def test_confirm_fires_once_per_chord_not_per_key(rig):
    """AnyKey stays held through a chord, so a second key isn't a second confirm."""
    _, widget, presses = rig
    press(widget, Qt.Key.Key_Space)
    press(widget, Qt.Key.Key_Z)
    release(widget, Qt.Key.Key_Space)
    press(widget, Qt.Key.Key_X)
    assert presses.count(UIAction.CONFIRM) == 1


def test_confirm_fires_when_a_real_key_joins_a_held_steering_key(rig):
    _, widget, presses = rig
    press(widget, Qt.Key.Key_Left)
    press(widget, Qt.Key.Key_Space)
    assert presses.count(UIAction.CONFIRM) == 1


# --- Focus and interruption ---------------------------------------------------


def test_focus_loss_releases_every_held_key(rig):
    """Guards against stuck keys: the release happens in another window and never arrives."""
    manager, widget, _ = rig
    for k in (Qt.Key.Key_Left, Qt.Key.Key_D, Qt.Key.Key_Space):
        press(widget, k)
    focus_out(widget)
    assert not any(
        manager.state.is_pressed(a) for a in ("left", "right", UIAction.CONFIRM)
    )


def test_release_after_focus_loss_and_regain_is_harmless(rig):
    manager, widget, presses = rig
    press(widget, Qt.Key.Key_Left)
    focus_out(widget)
    QApplication.sendEvent(widget, QFocusEvent(QEvent.Type.FocusIn))
    release(widget, Qt.Key.Key_Left)
    assert not manager.state.is_pressed("left")
    press(widget, Qt.Key.Key_Left)
    assert presses.count("left") == 2


def test_focus_loss_does_not_eat_the_focus_event(rig):
    manager, widget, _ = rig
    assert manager.eventFilter(widget, QFocusEvent(QEvent.Type.FocusOut)) is False


def test_switching_input_maps_carries_held_keys_without_firing(rig):
    """The key that launched an app must not also act inside it."""
    manager, widget, presses = rig
    press(widget, Qt.Key.Key_Space)
    presses.clear()
    manager.set_input_map(steering_map())
    assert manager.state.is_pressed(UIAction.CONFIRM)
    assert not manager.state.was_pressed(UIAction.CONFIRM)
    assert presses == []


def test_held_input_survives_a_pause_round_trip(host, input_manager, store):
    games: list[ProbeGame] = []

    def create(services):
        games.append(ProbeGame(services, store))
        return games[-1]

    host.switch_to(define(create, "probe"))
    game = games[0]
    to_playing(game)
    widget = QWidget()
    widget.installEventFilter(input_manager)
    press(widget, Qt.Key.Key_Space)
    press(widget, Qt.Key.Key_P)
    assert game.phase is Phase.PAUSED
    release(widget, Qt.Key.Key_P)
    press(widget, Qt.Key.Key_P)
    assert game.phase is Phase.PLAYING
    assert input_manager.state.is_pressed(UIAction.CONFIRM)
    widget.removeEventFilter(input_manager)


def test_a_tap_inside_one_frame_is_seen_by_exactly_one_step(host, input_manager, clock):
    """was_pressed must survive until a step reads it, then clear after exactly one."""
    seen: list[bool] = []
    apps: list[FakeApp] = []

    def create(services):
        app = FakeApp(services, steering_map())
        app.on_step = lambda a: seen.append(a.services.actions.was_pressed("left"))
        apps.append(app)
        return app

    host.switch_to(define(create))
    widget = QWidget()
    widget.installEventFilter(input_manager)
    press(widget, Qt.Key.Key_Left)
    release(widget, Qt.Key.Key_Left)
    clock.advance(0.1)
    host.tick()
    assert len(seen) > 1 and seen[0] is True and not any(seen[1:])
    widget.removeEventFilter(input_manager)


def test_quit_and_perf_are_handled_by_the_host_not_the_app(host, input_manager):
    apps: list[FakeApp] = []
    host.switch_to(define(lambda s: apps.append(FakeApp(s)) or apps[-1]))
    host.home = None
    host.exit_app = lambda: apps[0].calls.append("host-exit")  # type: ignore[method-assign]
    for action in (UIAction.QUIT, UIAction.TOGGLE_PERF, UIAction.PAUSE):
        input_manager.action_pressed.emit(action)
    assert host.perf.show_details is True
    assert "host-exit" in apps[0].calls
    assert ("action", UIAction.PAUSE) in apps[0].calls
    assert ("action", UIAction.QUIT) not in apps[0].calls
    assert ("action", UIAction.TOGGLE_PERF) not in apps[0].calls


# --- Gamepad and bindings ------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "left", "right"),
    [
        (-1.0, True, False),
        (-0.51, True, False),
        (-0.5, False, False),  # exactly the deadzone: must *exceed* it
        (0.0, False, False),
        (-0.0, False, False),
        (0.5, False, False),
        (0.500001, False, True),
        (1.0, False, True),
        (math.nan, False, False),  # a glitching driver must read as neutral
    ],
)
def test_stick_deadzone_boundaries(pad, x, left, right):
    manager = InputManager(steering_map(), gamepad_backend=pad)
    pad.state = GamepadState(left_stick=(x, 0.0))
    manager.poll()
    assert (manager.state.is_pressed("left"), manager.state.is_pressed("right")) == (
        left,
        right,
    )


def test_gamepad_and_keyboard_combine_and_release_independently(pad, rig):
    manager, widget, presses = rig
    pad.state = GamepadState(buttons=frozenset({GamepadButton.DPAD_LEFT}))
    manager.poll()
    press(widget, Qt.Key.Key_Left)
    pad.state = GamepadState()
    manager.poll()
    assert manager.state.is_pressed("left")
    assert presses.count("left") == 1


def test_unchanged_pad_state_does_not_re_evaluate(pad):
    manager = InputManager(steering_map(), gamepad_backend=pad)
    fired: list[str] = []
    manager.action_pressed.connect(fired.append)
    pad.state = GamepadState(buttons=frozenset({GamepadButton.START}))
    for _ in range(100):
        manager.poll()
    assert fired.count(UIAction.PAUSE) == 1


def test_binding_strength_is_clamped_to_unit_range():
    devices = DeviceState(gamepad=GamepadState(left_stick=(math.inf, 0.0)))
    assert 0.0 <= PadAxis(GamepadAxis.LEFT_X).strength(devices) <= 1.0


def test_empty_action_never_fires_and_duplicates_are_rejected():
    m = InputMap()
    m.add_action("nothing")
    assert m.evaluate(DeviceState(keys=frozenset({int(Qt.Key.Key_A)}))) == {
        "nothing": 0.0
    }
    with pytest.raises(ValueError):
        m.add_action("nothing", Key(Qt.Key.Key_A))


def test_action_state_reports_presses_until_cleared():
    state = ActionState()
    assert state.apply({"a": 1.0}) == ["a"]
    assert state.apply({"a": 0.0}) == []
    assert state.was_pressed("a") and not state.is_pressed("a")
    state.clear_presses()
    assert not state.was_pressed("a")
    assert state.strength("never-registered") == 0.0


@pytest.mark.parametrize("magnitude", [0.0, 0.1, 0.24, 0.25, 0.7, 1.0, 1.5, 1e9])
@pytest.mark.parametrize("angle", [0.0, 0.7, math.pi / 2, 2.5, math.pi, -1.0])
def test_radial_deadzone_output_is_bounded_and_direction_preserving(magnitude, angle):
    sdl = pytest.importorskip("qade_engine.input.sdl_gamepad")
    x, y = magnitude * math.cos(angle), magnitude * math.sin(angle)
    ox, oy = sdl._apply_radial_deadzone(x, y, 0.24)
    out = math.hypot(ox, oy)
    assert out <= 1.0 + 1e-12
    if magnitude <= 0.24:
        assert out < 1e-12
    else:
        assert ox * x >= 0 and oy * y >= 0


def test_backend_is_closed_when_the_application_quits(pad, qapp):
    InputManager(InputMap(), gamepad_backend=pad)
    qapp.aboutToQuit.emit()
    assert pad.closed >= 1


def test_default_bindings_cover_pad_start_for_both_pause_and_confirm():
    """START both confirms and pauses; document it so a remap is deliberate."""
    m = steering_map()
    devices = DeviceState(
        gamepad=GamepadState(buttons=frozenset({GamepadButton.START}))
    )
    strengths = m.evaluate(devices)
    assert strengths[UIAction.PAUSE] == strengths[UIAction.CONFIRM] == 1.0
    assert PadButton(GamepadButton.START).strength(devices) == 1.0
