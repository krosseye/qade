# SPDX-License-Identifier: GPL-3.0-or-later
"""Actions every app gets: confirm, quit, pause and the performance toggle."""

from collections.abc import Iterable
from enum import StrEnum

from PySide6.QtCore import Qt

from .bindings import AnyKey, Key, PadAxis, PadButton
from .gamepad import GamepadAxis, GamepadButton
from .input_map import InputMap


class UIAction(StrEnum):
    """The standard UI actions.

    Attributes:
        CONFIRM: Dismisses a "press any key" screen.
        QUIT: Leaves the app, back to the launcher or out of the program.
        TOGGLE_PERF: Shows or hides extra rows in the HUD's systems panel.
        PAUSE: Pauses or resumes play.
    """

    CONFIRM = "confirm"
    QUIT = "quit"
    TOGGLE_PERF = "toggle_perf"
    PAUSE = "pause"


QUIT_KEY = Qt.Key.Key_Escape
TOGGLE_PERF_KEY = Qt.Key.Key_F3
PAUSE_KEY = Qt.Key.Key_P
SYSTEM_KEYS = (
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Meta,
    Qt.Key.Key_Super_L,
    Qt.Key.Key_Super_R,
)

FACE_BUTTONS = (
    PadButton(GamepadButton.SOUTH),
    PadButton(GamepadButton.EAST),
    PadButton(GamepadButton.WEST),
    PadButton(GamepadButton.NORTH),
)


def add_ui_actions(
    input_map: InputMap, never_confirm: Iterable[Qt.Key] = ()
) -> InputMap:
    """Adds the standard UI actions to a game's input map.

    Args:
        input_map: The game's map, with its own actions already added.
        never_confirm: Keys that must not dismiss "press any key" screens,
            typically steering, so a player still turning at death doesn't
            skip past the game-over screen.

    Returns:
        The same map, for chaining.
    """
    input_map.add_action(
        UIAction.CONFIRM,
        AnyKey(
            exclude=frozenset(
                {*never_confirm, *SYSTEM_KEYS, QUIT_KEY, TOGGLE_PERF_KEY, PAUSE_KEY}
            )
        ),
        *FACE_BUTTONS,
        PadButton(GamepadButton.START),
    )
    input_map.add_action(UIAction.QUIT, Key(QUIT_KEY), PadButton(GamepadButton.SELECT))
    input_map.add_action(UIAction.TOGGLE_PERF, Key(TOGGLE_PERF_KEY))
    input_map.add_action(UIAction.PAUSE, Key(PAUSE_KEY), PadButton(GamepadButton.START))
    return input_map


def add_steering(
    input_map: InputMap,
    left: str,
    right: str,
    left_keys: Iterable[Qt.Key],
    right_keys: Iterable[Qt.Key],
) -> None:
    """Adds a left and a right action.

    Each is bound to the keys given, and to either stick, the d-pad, the
    bumpers and the triggers.

    Args:
        input_map: The map to add to.
        left: Name of the left action.
        right: Name of the right action.
        left_keys: Keys that steer left.
        right_keys: Keys that steer right.
    """
    input_map.add_action(
        left,
        *(Key(key) for key in left_keys),
        PadAxis(GamepadAxis.LEFT_X, -1),
        PadAxis(GamepadAxis.RIGHT_X, -1),
        PadAxis(GamepadAxis.LEFT_TRIGGER),
        PadButton(GamepadButton.L1),
        PadButton(GamepadButton.DPAD_LEFT),
    )
    input_map.add_action(
        right,
        *(Key(key) for key in right_keys),
        PadAxis(GamepadAxis.LEFT_X),
        PadAxis(GamepadAxis.RIGHT_X),
        PadAxis(GamepadAxis.RIGHT_TRIGGER),
        PadButton(GamepadButton.R1),
        PadButton(GamepadButton.DPAD_RIGHT),
    )
