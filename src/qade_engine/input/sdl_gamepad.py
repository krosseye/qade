# SPDX-License-Identifier: GPL-3.0-or-later
"""The SDL2 gamepad backend.

SDL2's game controller layer maps Xbox, DualShock, DualSense, Switch Pro and
most generic pads to one button layout, so one backend covers them all.
"""

import ctypes
import math

import sdl2

from .gamepad import GamepadButton, GamepadInfo, GamepadState

_AXIS_MAX = 32767.0

_BUTTON_NAMES = {
    sdl2.SDL_CONTROLLER_BUTTON_A: GamepadButton.SOUTH,
    sdl2.SDL_CONTROLLER_BUTTON_B: GamepadButton.EAST,
    sdl2.SDL_CONTROLLER_BUTTON_X: GamepadButton.WEST,
    sdl2.SDL_CONTROLLER_BUTTON_Y: GamepadButton.NORTH,
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER: GamepadButton.L1,
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: GamepadButton.R1,
    sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK: GamepadButton.L3,
    sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK: GamepadButton.R3,
    sdl2.SDL_CONTROLLER_BUTTON_START: GamepadButton.START,
    sdl2.SDL_CONTROLLER_BUTTON_BACK: GamepadButton.SELECT,
    sdl2.SDL_CONTROLLER_BUTTON_GUIDE: GamepadButton.GUIDE,
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP: GamepadButton.DPAD_UP,
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN: GamepadButton.DPAD_DOWN,
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT: GamepadButton.DPAD_LEFT,
    sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT: GamepadButton.DPAD_RIGHT,
}


def _apply_radial_deadzone(x: float, y: float, deadzone: float) -> tuple[float, float]:
    magnitude = math.hypot(x, y)
    if magnitude <= deadzone:
        return 0.0, 0.0
    scale = (min(magnitude, 1.0) - deadzone) / (1.0 - deadzone) / magnitude
    return x * scale, y * scale


class SDLGamepadBackend:
    """Tracks one primary game controller through SDL2, with hotplug support.

    The first available controller becomes the primary. If it is unplugged,
    the backend falls back to any other connected controller, and picks up a
    newly plugged-in one when none is active.
    """

    def __init__(
        self,
        stick_deadzone: float = 0.24,
        trigger_deadzone: float = 0.03,
        trigger_press_threshold: float = 0.5,
    ) -> None:
        """Starts SDL and opens the first controller, if any.

        Args:
            stick_deadzone: Radial deadzone for both sticks, from 0 to 1.
            trigger_deadzone: Trigger values below this read as 0.
            trigger_press_threshold: Trigger depth at which L2 and R2 count as
                pressed buttons.

        Raises:
            RuntimeError: SDL fails to start.
        """
        self._stick_deadzone = stick_deadzone
        self._trigger_deadzone = trigger_deadzone
        self._trigger_press_threshold = trigger_press_threshold

        self._controller = None
        self._instance_id = -1
        self._info: GamepadInfo | None = None

        sdl2.SDL_SetHint(b"SDL_GAMECONTROLLER_USE_BUTTON_LABELS", b"0")
        sdl2.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")

        if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER) < 0:
            error = sdl2.SDL_GetError().decode("utf-8")
            raise RuntimeError(f"Failed to initialize SDL: {error}")

        self._open_first_available()

    def poll(self) -> GamepadState:
        """Handles plugging and unplugging, then reads the primary controller.

        Returns:
            The controller's state, or an empty state if none is connected.
        """
        self._process_events()

        controller = self._controller
        if controller is None:
            return GamepadState()

        left_trigger = self._trigger(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT)
        right_trigger = self._trigger(controller, sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT)

        buttons = {
            name
            for constant, name in _BUTTON_NAMES.items()
            if sdl2.SDL_GameControllerGetButton(controller, constant)
        }
        if left_trigger >= self._trigger_press_threshold:
            buttons.add(GamepadButton.L2)
        if right_trigger >= self._trigger_press_threshold:
            buttons.add(GamepadButton.R2)

        return GamepadState(
            device=self._info,
            buttons=frozenset(buttons),
            left_stick=self._stick(
                controller,
                sdl2.SDL_CONTROLLER_AXIS_LEFTX,
                sdl2.SDL_CONTROLLER_AXIS_LEFTY,
            ),
            right_stick=self._stick(
                controller,
                sdl2.SDL_CONTROLLER_AXIS_RIGHTX,
                sdl2.SDL_CONTROLLER_AXIS_RIGHTY,
            ),
            left_trigger=left_trigger,
            right_trigger=right_trigger,
        )

    def close(self) -> None:
        """Releases the controller and shuts SDL down."""
        self._detach()
        sdl2.SDL_Quit()

    def _open_first_available(self) -> None:
        for index in range(sdl2.SDL_NumJoysticks()):
            if not sdl2.SDL_IsGameController(index):
                continue
            controller = sdl2.SDL_GameControllerOpen(index)
            if controller:
                self._attach(controller)
                return

    def _attach(self, controller) -> None:
        joystick = sdl2.SDL_GameControllerGetJoystick(controller)
        raw_name = sdl2.SDL_GameControllerName(controller)

        self._controller = controller
        self._instance_id = sdl2.SDL_JoystickInstanceID(joystick)
        self._info = GamepadInfo(
            name=raw_name.decode("utf-8") if raw_name else "Unknown gamepad",
            guid=bytes(sdl2.SDL_JoystickGetGUID(joystick).data).hex(),
        )

    def _detach(self) -> None:
        if self._controller is not None:
            sdl2.SDL_GameControllerClose(self._controller)
        self._controller = None
        self._instance_id = -1
        self._info = None

    def _process_events(self) -> None:
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)):
            if event.type == sdl2.SDL_CONTROLLERDEVICEADDED:
                if self._controller is None:
                    self._open_first_available()
            elif (
                event.type == sdl2.SDL_CONTROLLERDEVICEREMOVED
                and event.cdevice.which == self._instance_id
            ):
                self._detach()
                self._open_first_available()

    @staticmethod
    def _axis(controller, axis: int) -> float:
        return max(-1.0, sdl2.SDL_GameControllerGetAxis(controller, axis) / _AXIS_MAX)

    def _stick(self, controller, axis_x: int, axis_y: int) -> tuple[float, float]:
        x = self._axis(controller, axis_x)
        y = -self._axis(controller, axis_y)  # SDL reports +y as down; we use +y up.
        return _apply_radial_deadzone(x, y, self._stick_deadzone)

    def _trigger(self, controller, axis: int) -> float:
        value = self._axis(controller, axis)
        return value if value > self._trigger_deadzone else 0.0
