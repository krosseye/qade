# SPDX-License-Identifier: GPL-3.0-or-later
"""The launcher's controls: walk the aisle either way, on keys, sticks, d-pad
and bumpers."""

from enum import StrEnum

from PySide6.QtCore import Qt

from qade_engine.input import (
    GamepadAxis,
    GamepadButton,
    InputMap,
    Key,
    PadAxis,
    PadButton,
    add_ui_actions,
)


class Action(StrEnum):
    PREVIOUS = "previous"
    NEXT = "next"


_PREVIOUS_KEYS = (Qt.Key.Key_Left, Qt.Key.Key_A, Qt.Key.Key_Down, Qt.Key.Key_S)
_NEXT_KEYS = (Qt.Key.Key_Right, Qt.Key.Key_D, Qt.Key.Key_Up, Qt.Key.Key_W)


def input_map() -> InputMap:
    """A new InputMap with PREVIOUS, NEXT and the engine's UI actions."""
    controls = InputMap()
    controls.add_action(
        Action.PREVIOUS,
        *(Key(key) for key in _PREVIOUS_KEYS),
        PadAxis(GamepadAxis.LEFT_X, -1),
        PadAxis(GamepadAxis.RIGHT_X, -1),
        PadAxis(GamepadAxis.LEFT_Y, -1),
        PadAxis(GamepadAxis.RIGHT_Y, -1),
        PadButton(GamepadButton.DPAD_LEFT),
        PadButton(GamepadButton.DPAD_DOWN),
        PadButton(GamepadButton.L1),
    )
    controls.add_action(
        Action.NEXT,
        *(Key(key) for key in _NEXT_KEYS),
        PadAxis(GamepadAxis.LEFT_X),
        PadAxis(GamepadAxis.RIGHT_X),
        PadAxis(GamepadAxis.LEFT_Y),
        PadAxis(GamepadAxis.RIGHT_Y),
        PadButton(GamepadButton.DPAD_RIGHT),
        PadButton(GamepadButton.DPAD_UP),
        PadButton(GamepadButton.R1),
    )
    return add_ui_actions(controls, never_confirm=(*_PREVIOUS_KEYS, *_NEXT_KEYS))
