# SPDX-License-Identifier: GPL-3.0-or-later
"""Physical inputs that can be bound to actions."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from PySide6.QtCore import Qt

from .gamepad import GamepadAxis, GamepadButton, GamepadState


@dataclass(frozen=True, slots=True)
class DeviceState:
    """A snapshot of every input device at one moment.

    Attributes:
        keys: The keys held.
        gamepad: The primary gamepad.
    """

    keys: frozenset[int] = frozenset()
    gamepad: GamepadState = field(default_factory=GamepadState)


class Binding(Protocol):
    """Anything that can report how strongly it is being pressed."""

    def strength(self, devices: DeviceState) -> float:
        """How strongly this input is pressed, from 0 to 1.

        Args:
            devices: The snapshot to read.
        """
        ...


@dataclass(frozen=True, slots=True)
class Key:
    """A single keyboard key.

    Attributes:
        key: The key.
    """

    key: Qt.Key

    def strength(self, devices: DeviceState) -> float:
        return 1.0 if self.key in devices.keys else 0.0


@dataclass(frozen=True, slots=True)
class AnyKey:
    """Any keyboard key, apart from some.

    Attributes:
        exclude: Keys that don't count.
    """

    exclude: frozenset[Qt.Key] = field(default_factory=frozenset)

    def strength(self, devices: DeviceState) -> float:
        return 1.0 if any(k not in self.exclude for k in devices.keys) else 0.0


@dataclass(frozen=True, slots=True)
class PadButton:
    """A single gamepad button.

    Attributes:
        button: The button.
    """

    button: GamepadButton

    def strength(self, devices: DeviceState) -> float:
        return 1.0 if self.button in devices.gamepad.buttons else 0.0


@dataclass(frozen=True, slots=True)
class PadAxis:
    """One direction of a gamepad axis.

    Attributes:
        axis: The axis.
        direction: 1 reads the positive half. -1 reads the negative half
            (stick left or down), so one axis can drive two opposing actions.
    """

    axis: GamepadAxis
    direction: Literal[1, -1] = 1

    def strength(self, devices: DeviceState) -> float:
        return max(0.0, devices.gamepad.axis(self.axis) * self.direction)
