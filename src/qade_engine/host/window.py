# SPDX-License-Identifier: GPL-3.0-or-later
"""The application window."""

from PySide6.QtCore import QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow

from qade_engine.input.input_map import InputMap
from qade_engine.input.manager import InputManager
from qade_engine.resources import resource_path

from .app import GameDefinition, GameInfo, HostSettings
from .host import Host
from .view import create_view
from .win32 import keep_composited


class HostWindow(QMainWindow):
    """The application window: one view and one host, whichever app is running.

    Attributes:
        input: Keyboard and gamepad input.
        host: Runs the apps.
        view: The drawing surface.
    """

    def __init__(
        self,
        definition: GameDefinition,
        settings: HostSettings,
        refresh_rate: float,
        home: GameDefinition | None = None,
    ) -> None:
        """Creates the window and starts the first app.

        Args:
            definition: The app to start.
            settings: The player's options.
            refresh_rate: Display refresh rate in Hz.
            home: The app to return to when a game quits, such as a launcher.
        """
        super().__init__()
        self.input = InputManager(InputMap(), parent=self)
        self.host = Host(
            self.input,
            settings,
            refresh_rate,
            home=home,
            parent=self,
        )
        self.view = create_view(self.host, not settings.software_renderer)
        self.view.installEventFilter(self.input)
        self.host.app_changed.connect(self._on_app_changed)
        self.setCentralWidget(self.view)

        self.host.switch_to(definition)
        if self.host.app is not None:
            self.resize(*self.host.app.canvas_size)
        if settings.fullscreen:
            self.showFullScreen()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        keep_composited(self)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            keep_composited(self)

    def _on_app_changed(self, info: GameInfo) -> None:
        self.setWindowTitle(info.title)
        icon = resource_path(info.package, "icon.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
