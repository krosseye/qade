# SPDX-License-Identifier: GPL-3.0-or-later
"""Input for games: named actions, bound to keys and gamepad inputs."""

from .actions import FACE_BUTTONS, UIAction, add_steering, add_ui_actions
from .bindings import Key, PadAxis, PadButton
from .gamepad import GamepadAxis, GamepadButton
from .input_map import InputMap
from .state import ActionState

__all__ = [
    "FACE_BUTTONS",
    "ActionState",
    "GamepadAxis",
    "GamepadButton",
    "InputMap",
    "Key",
    "PadAxis",
    "PadButton",
    "UIAction",
    "add_steering",
    "add_ui_actions",
]
