# SPDX-License-Identifier: GPL-3.0-or-later
"""The host: runs one app at a time and owns the loop, input routing and perf meters."""

import logging
from collections.abc import Callable
from functools import partial
from time import perf_counter

from PySide6.QtCore import QCoreApplication, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPainter

from qade_engine.core.timestep import FixedTimestep
from qade_engine.graphics.palette import BLACK
from qade_engine.graphics.viewport import Viewport
from qade_engine.input.actions import UIAction
from qade_engine.input.manager import InputManager
from qade_engine.perf import FrameStats, PerfStats

from .app import App, Frame, GameDefinition, GameInfo, HostSettings, Services

_log = logging.getLogger(__name__)

MAX_FRAME_DT = 0.25
TICK_INTERVAL_MS = 15


class Host(QObject):
    """Runs apps inside one window: the loop timers, input routing and perf.

    Everything runs on the Qt main thread, so nothing interleaves:

    * Key events update input as they arrive. QUIT and TOGGLE_PERF are
      handled by the host, other one-shot actions by the running app.
    * Each tick samples the gamepad, then runs the app's fixed steps that are
      due. The view ticks just before it paints, so a frame always draws the
      simulation as of that moment.
    * While the player is away the host is suspended: no input, no steps, and
      real time spent away is skipped, never caught up.
    * The first exception an app raises is logged and the app is left. It is
      never called again, so a bug can't repeat every tick.

    Attributes:
        frame_due: Emitted when the raster view should repaint.
        app_changed: Emitted with the ``GameInfo`` of a newly running app.
        app: The running app, if any.
        info: The running app's identity, if any.
        home: The app to return to when a game quits, if any.
        perf: Measurements shown in the HUD.
    """

    frame_due = Signal()
    app_changed = Signal(object)

    def __init__(
        self,
        input_manager: InputManager,
        settings: HostSettings,
        refresh_rate: float,
        home: GameDefinition | None = None,
        parent: QObject | None = None,
    ):
        """Creates the host and starts its timers. No app runs until ``switch_to``.

        Args:
            input_manager: Keyboard and gamepad input, shared by every app.
            settings: Options passed to every app.
            refresh_rate: Display refresh rate in Hz. Sets the frame timer.
            home: The app to return to when a game quits, such as a launcher.
            parent: The owning Qt object.
        """
        super().__init__(parent)
        self.input = input_manager
        self.settings = settings
        self.home = home
        self.perf = PerfStats(target_fps=float(refresh_rate))
        self.fps = FrameStats()
        self.ups = FrameStats()

        self.app: App | None = None
        self.info: GameInfo | None = None
        self._services = Services()
        self._timestep = FixedTimestep(1.0)
        self._request: Callable[[], None] | None = None
        self._failed = False
        self._suspended = False
        input_manager.action_pressed.connect(self._on_action)
        application = QGuiApplication.instance()
        if isinstance(application, QGuiApplication):
            application.applicationStateChanged.connect(self._on_application_state)

        self._last_tick_time = perf_counter()
        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.timeout.connect(self.tick)
        self._frame_timer = QTimer(self)
        self._frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._frame_timer.timeout.connect(self.frame_due)
        self._tick_timer.start(TICK_INTERVAL_MS)
        self._frame_timer.start(max(1, int(1000 / refresh_rate)))

    def switch_to(self, definition: GameDefinition) -> None:
        """Replaces the running app, if any, with a new one.

        The new app is built first, so one that fails to build leaves the
        running app as it was.

        Args:
            definition: The app to build and start.

        Raises:
            ValueError: The new app's input map has no quit action.
        """
        services = Services(
            actions=self.input.state,
            settings=self.settings,
            window_size=self._services.window_size,
            exit=partial(self._later, self.exit_app),
            launch=lambda definition: self._later(partial(self.switch_to, definition)),
        )
        app = definition.create(services)
        if UIAction.QUIT not in app.input_map:
            raise ValueError(f"{definition.info.id}: input map has no quit action")
        self._stop_app()
        self._services = services
        self.input.set_input_map(app.input_map)
        self.perf.target_ups = float(app.tick_hz)
        self._timestep = FixedTimestep(1.0 / app.tick_hz)
        self.app, self.info = app, definition.info
        self._failed = False
        self._last_tick_time = perf_counter()
        self._call("start", app.start)
        if self._suspended:
            self._call("suspend", app.suspend)
        self.app_changed.emit(definition.info)

    def _stop_app(self) -> None:
        """Stops the running app, even one that raised: it may still hold audio."""
        if self.app is None:
            return
        try:
            self.app.stop()
        except Exception:  # noqa: BLE001 -- any bug in an app, by design
            _log.exception(
                "%s raised while stopping", self.info.id if self.info else "app"
            )

    def _call(self, where: str, method: Callable, *args) -> bool:
        """Calls into the running app, unless it has already raised.

        The first exception is logged, and the app is left once the current
        tick or event is over.

        Returns:
            False if the app raised, now or before.
        """
        if self._failed:
            return False
        try:
            method(*args)
        except Exception:  # noqa: BLE001 -- any bug in an app, by design
            self._failed = True
            name = self.info.id if self.info else "app"
            _log.exception("%s raised in %s: leaving it", name, where)
            self._later(self.exit_app)
            return False
        return True

    def _later(self, request: Callable[[], None]) -> None:
        """Runs an exit or launch once the current tick or event is over.

        An app is then never stopped in the middle of its own step. Only the
        last request before then counts.
        """
        if self._request is None:
            QTimer.singleShot(0, self._run_request)
        self._request = request

    def _run_request(self) -> None:
        request, self._request = self._request, None
        if request is not None:
            request()

    def exit_app(self) -> None:
        """Leaves the running app: back to ``home``, or quits if this is home."""
        if self.home is not None and self.info != self.home.info:
            self.switch_to(self.home)
        else:
            self.shutdown()
            QCoreApplication.quit()

    def shutdown(self) -> None:
        """Stops the loop and the running app."""
        self._tick_timer.stop()
        self._frame_timer.stop()
        self._request = None
        self._stop_app()
        self.app = None  # quitting runs this twice: never stop an app twice

    def _on_action(self, action: str) -> None:
        match action:
            case UIAction.QUIT:
                self.exit_app()
            case UIAction.TOGGLE_PERF:
                self.perf.show_details = not self.perf.show_details
            case _:
                if self.app is not None:
                    self._call("on_action", self.app.on_action, action)

    def _on_application_state(self, state: Qt.ApplicationState) -> None:
        self.set_suspended(state != Qt.ApplicationState.ApplicationActive)

    def set_suspended(self, suspended: bool) -> None:
        """Holds the app still while the player is away, and tells it.

        Args:
            suspended: True when the application becomes inactive (minimised,
                Alt-Tab), False when it is active again.
        """
        if suspended == self._suspended:
            return
        self._suspended = suspended
        if self.app is not None:
            if suspended:
                self._call("suspend", self.app.suspend)
            else:
                self._call("resume", self.app.resume)

    def tick(self) -> None:
        """Runs the app's fixed steps that are due by now."""
        now = perf_counter()
        dt = min(now - self._last_tick_time, MAX_FRAME_DT)
        self._last_tick_time = now

        steps = 0
        if not self._suspended:
            self.input.poll()
            if self.app is not None:
                steps = self._timestep.advance(dt)
                for _ in range(steps):
                    if not self._call("step", self.app.step, self._timestep.step):
                        break
                    self.input.state.clear_presses()

        self.ups.tick(steps)
        self.perf.ups = self.ups.rate

    def on_resized(self, size: tuple[int, int]) -> None:
        """Records the view's new size.

        Args:
            size: Width and height in logical pixels, as ``widget.width()``
                reports them.
        """
        self._services.window_size = size

    def paint(self, painter: QPainter, widget_size: tuple[int, int]) -> None:
        """Draws the running app, scaled to fit the widget.

        Args:
            painter: A painter on the view.
            widget_size: The view's size in logical pixels.
        """
        width, height = widget_size
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing,
            True,
        )
        painter.fillRect(0, 0, width, height, BLACK)
        if self.app is None:
            return

        view = Viewport.fit(widget_size, self.app.canvas_size)
        painter.scale(view.scale, view.scale)
        frame = Frame(
            painter=painter,
            view=view,
            now=perf_counter(),
            perf=self.perf,
            alpha=self._timestep.alpha,
        )
        self._call("draw", self.app.draw, frame)

    def on_painted(self) -> None:
        """Counts one painted frame."""
        self.fps.tick()
        self.perf.fps = self.fps.rate
        self.perf.frame_ms = self.fps.avg_ms
        self.perf.worst_ms = self.fps.worst_ms

    def on_paint_finished(self, ms: float) -> None:
        """Records how long a paint took.

        Args:
            ms: Milliseconds the paint handler took.
        """
        self.perf.record_paint_time(ms)
