# SPDX-License-Identifier: GPL-3.0-or-later
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
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ACT = "act"  # hold: plant your feet


_KEYS = {
    Action.UP: (Qt.Key.Key_Up, Qt.Key.Key_W),
    Action.DOWN: (Qt.Key.Key_Down, Qt.Key.Key_S),
    Action.LEFT: (Qt.Key.Key_Left, Qt.Key.Key_A),
    Action.RIGHT: (Qt.Key.Key_Right, Qt.Key.Key_D),
}
_PAD = {
    Action.UP: (PadButton(GamepadButton.DPAD_UP), PadAxis(GamepadAxis.LEFT_Y)),
    Action.DOWN: (PadButton(GamepadButton.DPAD_DOWN), PadAxis(GamepadAxis.LEFT_Y, -1)),
    Action.LEFT: (PadButton(GamepadButton.DPAD_LEFT), PadAxis(GamepadAxis.LEFT_X, -1)),
    Action.RIGHT: (PadButton(GamepadButton.DPAD_RIGHT), PadAxis(GamepadAxis.LEFT_X)),
}
_ACT_KEYS = (Qt.Key.Key_Space, Qt.Key.Key_E, Qt.Key.Key_Return, Qt.Key.Key_Enter)
MOVEMENT_KEYS = tuple(key for keys in _KEYS.values() for key in keys)


def input_map() -> InputMap:
    controls = InputMap()
    for action, keys in _KEYS.items():
        controls.add_action(action, *(Key(key) for key in keys), *_PAD[action])
    controls.add_action(
        Action.ACT,
        *(Key(key) for key in _ACT_KEYS),
        *FACE_BUTTONS,
        PadAxis(GamepadAxis.LEFT_TRIGGER),
        PadAxis(GamepadAxis.RIGHT_TRIGGER),
    )
    return controls
