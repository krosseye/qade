# SPDX-License-Identifier: GPL-3.0-or-later
"""The window's drawing surface: OpenGL-backed, or software raster."""

from time import perf_counter

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPaintEvent, QResizeEvent, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

from .host import Host

MSAA_SAMPLES = 4


def use_opengl_format() -> None:
    """Asks for multisampling and vsync. Call before the QApplication exists."""
    surface_format = QSurfaceFormat.defaultFormat()
    surface_format.setSamples(MSAA_SAMPLES)
    surface_format.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(surface_format)


def create_view(host: Host, use_hardware: bool) -> QWidget:
    """Creates a view that paints whatever the host is running, once per display frame.

    Args:
        host: The host to paint.
        use_hardware: True for the OpenGL view, paced by vsync. False for the
            raster view, paced by the host's frame timer.

    Returns:
        The view.
    """
    view: QWidget
    if use_hardware:
        view = OpenGLView(host)
    else:
        view = RasterView(host)
        host.frame_due.connect(view.update)
    view.setCursor(Qt.CursorShape.BlankCursor)
    view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return view


def _paint(widget: QWidget, host: Host) -> None:
    host.tick()
    host.on_painted()
    start = perf_counter()
    painter = QPainter(widget)
    try:
        host.paint(painter, (widget.width(), widget.height()))
    finally:
        painter.end()
    host.on_paint_finished((perf_counter() - start) * 1000.0)


class OpenGLView(QOpenGLWidget):
    """A view paced by vsync: each frame shown asks for the next.

    Showing the window starts the loop, and so does showing it again after it
    was minimised.
    """

    def __init__(self, host: Host) -> None:
        """Creates the view.

        Args:
            host: The host to paint.
        """
        super().__init__()
        self.host = host
        self._min_interval = 0.9 / host.perf.target_fps
        self._last_request = 0.0
        self.frameSwapped.connect(self._next_frame)

    def paintGL(self) -> None:
        _paint(self, self.host)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.host.on_resized((self.width(), self.height()))

    def _next_frame(self) -> None:
        wait = self._min_interval - (perf_counter() - self._last_request)
        if wait > 0.001:
            QTimer.singleShot(int(wait * 1000), self._request)
        else:
            self._request()

    def _request(self) -> None:
        self._last_request = perf_counter()
        self.update()


class RasterView(QWidget):
    """A software-rendered view, repainted when the host's frame timer fires."""

    def __init__(self, host: Host) -> None:
        """Creates the view.

        Args:
            host: The host to paint.
        """
        super().__init__()
        self.host = host

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        _paint(self, self.host)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.host.on_resized((self.width(), self.height()))
