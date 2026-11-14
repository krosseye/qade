# SPDX-License-Identifier: GPL-3.0-or-later
"""Gamepad data, and the contract a gamepad backend meets."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class GamepadButton(StrEnum):
    """Buttons named by position, the same on every pad."""

    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTH = "north"
    L1 = "l1"
    R1 = "r1"
    L2 = "l2"
    R2 = "r2"
    L3 = "l3"
    R3 = "r3"
    START = "start"
    SELECT = "select"
    GUIDE = "guide"
    DPAD_UP = "dpad_up"
    DPAD_DOWN = "dpad_down"
    DPAD_LEFT = "dpad_left"
    DPAD_RIGHT = "dpad_right"


class GamepadAxis(StrEnum):
    """Analog inputs. Sticks span -1 to 1, +x right and +y up; triggers 0 to 1."""

    LEFT_X = "left_x"
    LEFT_Y = "left_y"
    RIGHT_X = "right_x"
    RIGHT_Y = "right_y"
    LEFT_TRIGGER = "left_trigger"
    RIGHT_TRIGGER = "right_trigger"


@dataclass(frozen=True, slots=True)
class GamepadInfo:
    """Identifies a connected controller.

    Attributes:
        name: The controller's name.
        guid: The hardware model's GUID, the same for every pad of one model.
    """

    name: str
    guid: str


@dataclass(frozen=True, slots=True)
class GamepadState:
    """A hardware-independent snapshot of the primary gamepad.

    Attributes:
        device: The controller, or None if none is connected.
        buttons: The ``GamepadButton`` names held.
        left_stick: (x, y) from -1 to 1, +x right and +y up, after the deadzone.
        right_stick: As ``left_stick``.
        left_trigger: From 0 to 1.
        right_trigger: From 0 to 1.
    """

    device: GamepadInfo | None = None
    buttons: frozenset[str] = frozenset()
    left_stick: tuple[float, float] = (0.0, 0.0)
    right_stick: tuple[float, float] = (0.0, 0.0)
    left_trigger: float = 0.0
    right_trigger: float = 0.0

    def axis(self, axis: GamepadAxis) -> float:
        """Reads one analog axis.

        Args:
            axis: The axis.

        Returns:
            Its current value.
        """
        match axis:
            case GamepadAxis.LEFT_X:
                return self.left_stick[0]
            case GamepadAxis.LEFT_Y:
                return self.left_stick[1]
            case GamepadAxis.RIGHT_X:
                return self.right_stick[0]
            case GamepadAxis.RIGHT_Y:
                return self.right_stick[1]
            case GamepadAxis.LEFT_TRIGGER:
                return self.left_trigger
            case GamepadAxis.RIGHT_TRIGGER:
                return self.right_trigger


class GamepadBackend(Protocol):
    """Anything that can produce gamepad snapshots."""

    def poll(self) -> GamepadState:
        """Reads the gamepad now."""
        ...

    def close(self) -> None:
        """Releases the device."""
        ...


class NullGamepad:
    """A backend with no gamepad, used when none can be opened."""

    def poll(self) -> GamepadState:
        return GamepadState()

    def close(self) -> None:
        pass
