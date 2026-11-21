# SPDX-License-Identifier: GPL-3.0-or-later
"""Turns keyboard and gamepad input into action events."""

import logging

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal
from PySide6.QtGui import QKeyEvent

from .bindings import DeviceState
from .gamepad import GamepadBackend, GamepadState, NullGamepad
from .input_map import InputMap
from .state import ActionState

_log = logging.getLogger(__name__)


def _default_backend() -> GamepadBackend:
    """SDL, or no gamepad at all if it can't load or start."""
    try:
        from .sdl_gamepad import SDLGamepadBackend

        return SDLGamepadBackend()
    except (ImportError, RuntimeError) as exc:
        _log.warning("gamepads unavailable: %s", exc)
        return NullGamepad()


class InputManager(QObject):
    """Tracks every input device and resolves it into actions.

    Install it as an event filter on the widget that has keyboard focus, and
    call ``poll`` once per tick to sample the gamepad.

    Attributes:
        action_pressed: Emitted with an action's name as it is pressed.
        input_map: The running app's actions.
        state: Every action's current strength.
    """

    action_pressed = Signal(str)

    def __init__(
        self,
        input_map: InputMap,
        gamepad_backend: GamepadBackend | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Starts tracking the keyboard and gamepad.

        Args:
            input_map: The actions and their bindings.
            gamepad_backend: Gamepad source. Defaults to SDL, or none if SDL
                is unavailable.
            parent: The owning Qt object.
        """
        super().__init__(parent)
        self.input_map = input_map
        self.state = ActionState()
        self._held_keys: set[int] = set()

        self._backend = gamepad_backend or _default_backend()
        self._pad = GamepadState()
        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self._backend.close)

    def poll(self) -> None:
        """Samples the gamepad. Keyboard input arrives through events instead."""
        pad = self._backend.poll()
        if pad != self._pad:
            self._pad = pad
            self._refresh()

    def set_input_map(self, input_map: InputMap) -> None:
        """Switches to another app's actions.

        Inputs already held carry over as held without firing presses, so the
        key that launched an app doesn't also act inside it.

        Args:
            input_map: The new app's actions.
        """
        self.input_map = input_map
        devices = DeviceState(frozenset(self._held_keys), self._pad)
        strengths = input_map.evaluate(devices)
        self.state.expect(strengths)
        self.state.apply(strengths)
        self.state.clear_presses()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Consumes every key event from the watched widget."""
        if isinstance(event, QKeyEvent):
            if not event.isAutoRepeat():
                if event.type() == QEvent.Type.KeyPress:
                    self._held_keys.add(event.key())
                    self._refresh()
                elif event.type() == QEvent.Type.KeyRelease:
                    self._held_keys.discard(event.key())
                    self._refresh()
            return True

        if event.type() == QEvent.Type.FocusOut and self._held_keys:
            self._held_keys.clear()
            self._refresh()

        return super().eventFilter(watched, event)

    def _refresh(self) -> None:
        devices = DeviceState(frozenset(self._held_keys), self._pad)
        for action in self.state.apply(self.input_map.evaluate(devices)):
            self.action_pressed.emit(action)
