# SPDX-License-Identifier: GPL-3.0-or-later
"""Named actions and the physical inputs bound to them."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from .bindings import Binding, DeviceState

DEFAULT_DEADZONE: float = 0.5


@dataclass(slots=True)
class _ActionSpec:
    deadzone: float
    bindings: list[Binding] = field(default_factory=list)


class InputMap:
    """A registry of actions, each triggered by any of its bindings.

    Example:
        ```python
        input_map = InputMap()
        input_map.add_action("jump", Key(Qt.Key.Key_Space), PadButton(GamepadButton.SOUTH))
        ```
    """

    def __init__(self) -> None:
        """Creates an empty map."""
        self._actions: dict[str, _ActionSpec] = {}

    def __contains__(self, action: str) -> bool:
        return action in self._actions

    def add_action(
        self, action: str, *bindings: Binding, deadzone: float = DEFAULT_DEADZONE
    ) -> None:
        """Registers an action.

        Args:
            action: The action's name.
            *bindings: Inputs that trigger it.
            deadzone: Strength it must exceed to count as pressed.

        Raises:
            ValueError: The action is already registered.
        """
        if action in self._actions:
            raise ValueError(f"Action already registered: {action!r}")
        self._actions[action] = _ActionSpec(deadzone, list(bindings))

    def evaluate(self, devices: DeviceState) -> dict[str, float]:
        """Resolves every action's strength for a device snapshot.

        Args:
            devices: The current state of every input device.

        Returns:
            Strength per action, in registration order: its strongest
            binding's, or 0 when that doesn't exceed the deadzone.
        """
        return {
            action: _strongest(spec.bindings, devices, spec.deadzone)
            for action, spec in self._actions.items()
        }


def _strongest(
    bindings: Iterable[Binding], devices: DeviceState, deadzone: float
) -> float:
    strength = max((binding.strength(devices) for binding in bindings), default=0.0)
    return strength if strength > deadzone else 0.0
