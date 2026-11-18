# SPDX-License-Identifier: GPL-3.0-or-later
"""Grizzly Depths actions and their default bindings."""

from enum import StrEnum

from PySide6.QtCore import Qt

from qade_engine.input import (
    FACE_BUTTONS,
    GamepadAxis,
    GamepadButton,
    InputMap,
    Key,
    PadAxis,
    PadButton,
)


class Action(StrEnum):
    FORWARD = "forward"
    BACK = "back"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    ATTUNE = "attune"  # held on the exit crystal


_KEYS = {
    Action.FORWARD: (Qt.Key.Key_Up, Qt.Key.Key_W),
    Action.BACK: (Qt.Key.Key_Down, Qt.Key.Key_S),
    Action.TURN_LEFT: (Qt.Key.Key_Left, Qt.Key.Key_A),
    Action.TURN_RIGHT: (Qt.Key.Key_Right, Qt.Key.Key_D),
}
_PAD = {
    Action.FORWARD: (
        PadButton(GamepadButton.DPAD_UP),
        PadAxis(GamepadAxis.LEFT_Y),
        PadAxis(GamepadAxis.RIGHT_Y),
    ),
    Action.BACK: (
        PadButton(GamepadButton.DPAD_DOWN),
        PadAxis(GamepadAxis.LEFT_Y, -1),
        PadAxis(GamepadAxis.RIGHT_Y, -1),
    ),
    Action.TURN_LEFT: (
        PadButton(GamepadButton.DPAD_LEFT),
        PadAxis(GamepadAxis.LEFT_X, -1),
        PadAxis(GamepadAxis.RIGHT_X, -1),
        PadButton(GamepadButton.L1),
    ),
    Action.TURN_RIGHT: (
        PadButton(GamepadButton.DPAD_RIGHT),
        PadAxis(GamepadAxis.LEFT_X),
        PadAxis(GamepadAxis.RIGHT_X),
        PadButton(GamepadButton.R1),
    ),
}
_ATTUNE_KEYS = (Qt.Key.Key_Space, Qt.Key.Key_E, Qt.Key.Key_Return, Qt.Key.Key_Enter)
MOVEMENT_KEYS = tuple(key for keys in _KEYS.values() for key in keys)


def input_map() -> InputMap:
    """A new InputMap binding every Action to its keys and gamepad inputs."""
    controls = InputMap()
    for action, keys in _KEYS.items():
        controls.add_action(action, *(Key(key) for key in keys), *_PAD[action])
    controls.add_action(
        Action.ATTUNE,
        *(Key(key) for key in _ATTUNE_KEYS),
        *FACE_BUTTONS,
        PadAxis(GamepadAxis.LEFT_TRIGGER),
        PadAxis(GamepadAxis.RIGHT_TRIGGER),
    )
    return controls
