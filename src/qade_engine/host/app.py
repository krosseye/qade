# SPDX-License-Identifier: GPL-3.0-or-later
"""The contract between the host and whatever it runs: a game, or a launcher."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from PySide6.QtGui import QPainter

from qade_engine.graphics.viewport import Viewport
from qade_engine.input.input_map import InputMap
from qade_engine.input.state import ActionState
from qade_engine.perf import PerfStats


@dataclass(frozen=True)
class GameInfo:
    """Identity of a game: everything a launcher needs to list it.

    Attributes:
        id: Stable and filesystem-safe. Names the game's save folder.
        title: Display name.
        package: Python package holding the game's ``resources`` folder.
        description: One line for a launcher.
        accent: A color name such as ``"#ffa500"`` for launcher art. Empty
            uses the theme's.
    """

    id: str
    title: str
    package: str
    description: str = ""
    accent: str = ""


@dataclass(frozen=True)
class HostSettings:
    """Options the player chose when starting the host.

    Attributes:
        use_tts: Speak the intro aloud.
        sound_effects: Play sound effects.
        music: Play music.
        fullscreen: Start fullscreen.
        software_renderer: Draw without OpenGL.
    """

    use_tts: bool = True
    sound_effects: bool = True
    music: bool = True
    fullscreen: bool = False
    software_renderer: bool = False


@dataclass
class Services:
    """What the host gives an app. The defaults run an app headless.

    Attributes:
        actions: Held input. Only changes between steps.
        settings: The player's options.
        exit: Leaves the app, back to the launcher or out of the program.
        launch: Switches to another app.
        window_size: The window's size in logical pixels, or None until it is
            first sized and always when headless. Only changes between steps.

    ``exit`` and ``launch`` act once the current step or event is over, so
    they are safe to call from ``step``. Of several calls before then, only
    the last counts.
    """

    actions: ActionState = field(default_factory=ActionState)
    settings: HostSettings = field(default_factory=HostSettings)
    exit: Callable[[], None] = lambda: None
    launch: Callable[["GameDefinition"], None] = lambda definition: None
    window_size: tuple[int, int] | None = None


@dataclass(frozen=True)
class Frame:
    """Everything an app needs to draw one frame.

    The painter is already scaled uniformly so the app's canvas fits the
    window in its shorter direction. ``view`` is the whole window in those
    units: at least the canvas size, and larger along the window's longer
    direction. Lay out against ``view.width`` and ``view.height``.

    The simulation runs at a fixed rate, not the display's. For smooth motion,
    blend the last two steps by ``alpha``, or move things on by ``alpha`` of a
    step.

    Attributes:
        painter: The painter to draw with.
        view: The window, in the painter's scaled units.
        now: Real-time seconds from an arbitrary start, not simulation time,
            for blinking and typing effects.
        alpha: How far into the next fixed step this frame is, from 0 to 1.
        perf: Performance measurements, for the HUD.
    """

    painter: QPainter
    view: Viewport
    now: float
    alpha: float
    perf: PerfStats


class App(Protocol):
    """Something the host can run.

    Attributes:
        canvas_size: Logical resolution. The host scales it to fit the window.
        tick_hz: Fixed steps per second.
        input_map: The app's actions. Must include ``UIAction.QUIT``.
    """

    canvas_size: tuple[int, int]
    tick_hz: int
    input_map: InputMap

    def start(self) -> None:
        """Becomes the running app: acquires audio and other live resources."""

    def stop(self) -> None:
        """Stops running: releases everything ``start`` acquired."""

    def suspend(self) -> None:
        """The player is away: pause play and silence anything playing.

        No steps run until ``resume``.
        """

    def resume(self) -> None:
        """The player is back. Steps run again."""

    def step(self, dt: float) -> None:
        """Advances one fixed step.

        Args:
            dt: Step length in seconds.
        """

    def on_action(self, action: str) -> None:
        """Handles a one-shot action the host didn't handle itself.

        Args:
            action: The action that was pressed.
        """

    def draw(self, frame: Frame) -> None:
        """Draws the current state without changing it.

        Args:
            frame: What to draw with.
        """


@dataclass(frozen=True)
class GameDefinition:
    """What a game package exports, so a host or launcher can run it.

    Attributes:
        info: The game's identity.
        create: Builds the game. Called only when it starts, so a launcher
            can list many games without building any.
    """

    info: GameInfo
    create: Callable[[Services], App]
