# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher controls: which inputs walk, and that walking never launches."""

import pytest

from qade_engine.input import GamepadButton, UIAction
from qade_engine.input.bindings import DeviceState
from qade_engine.input.gamepad import GamepadState
from qade_launcher.controls import _NEXT_KEYS, _PREVIOUS_KEYS, Action, input_map


def test_the_launcher_can_be_quit():
    assert UIAction.QUIT in input_map()


@pytest.mark.parametrize("key", _PREVIOUS_KEYS + _NEXT_KEYS)
def test_walk_keys_walk_one_way_and_never_launch(key):
    strengths = input_map().evaluate(DeviceState(keys=frozenset({int(key)})))
    walking = {a for a in (Action.PREVIOUS, Action.NEXT) if strengths[a] > 0}
    assert walking == {Action.NEXT if key in _NEXT_KEYS else Action.PREVIOUS}
    assert strengths[UIAction.CONFIRM] == 0


@pytest.mark.parametrize(
    ("stick", "expected"),
    [
        ((0.0, 1.0), Action.NEXT),
        ((0.0, -1.0), Action.PREVIOUS),
        ((1.0, 0.0), Action.NEXT),
        ((-1.0, 0.0), Action.PREVIOUS),
    ],
)
@pytest.mark.parametrize("which", ["left_stick", "right_stick"])
def test_sticks_walk_the_same_way_as_the_keys(stick, expected, which):
    pad = GamepadState(**{which: stick})
    strengths = input_map().evaluate(DeviceState(gamepad=pad))
    assert strengths[expected] > 0
    other = Action.PREVIOUS if expected is Action.NEXT else Action.NEXT
    assert strengths[other] == 0
    assert strengths[UIAction.CONFIRM] == 0


def test_a_resting_stick_inside_the_deadzone_does_not_walk():
    pad = GamepadState(left_stick=(0.45, -0.45), right_stick=(-0.3, 0.3))
    strengths = input_map().evaluate(DeviceState(gamepad=pad))
    assert strengths[Action.NEXT] == strengths[Action.PREVIOUS] == 0


@pytest.mark.parametrize(
    "button",
    [
        GamepadButton.DPAD_LEFT,
        GamepadButton.DPAD_RIGHT,
        GamepadButton.DPAD_UP,
        GamepadButton.DPAD_DOWN,
        GamepadButton.L1,
        GamepadButton.R1,
    ],
)
def test_walk_buttons_never_launch(button):
    pad = GamepadState(buttons=frozenset({button}))
    strengths = input_map().evaluate(DeviceState(gamepad=pad))
    assert strengths[UIAction.CONFIRM] == 0
    assert strengths[Action.NEXT] + strengths[Action.PREVIOUS] > 0
