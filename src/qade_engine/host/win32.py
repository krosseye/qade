# SPDX-License-Identifier: GPL-3.0-or-later
"""Windows-only fixes for the host window."""

import ctypes
import sys

from PySide6.QtWidgets import QMainWindow


def keep_composited(window: QMainWindow) -> None:
    """Keeps a fullscreen window composited on Windows. Does nothing elsewhere.

    Call it on every show and window state change.

    Args:
        window: The host window.
    """
    # A borderless window that exactly covers the screen skips the desktop
    # compositor, and an OpenGL view's buffer swaps then stall for several
    # refreshes at a time: judder, and late simulation ticks. A 1 px border
    # keeps it composited, as Qt's setHasBorderInFullScreen would (PySide
    # doesn't expose it). Qt redoes the style and corners on every show and
    # state change, hence calling this on each.
    if sys.platform != "win32" or not window.isFullScreen():
        return
    user32 = ctypes.WinDLL("user32")  # its own handle: argtypes stay local
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int)
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_ssize_t,
    )
    gwl_style, ws_border = -16, 0x00800000
    # SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
    flags = 0x0004 | 0x0010 | 0x0020

    handle = int(window.winId())
    style = user32.GetWindowLongPtrW(handle, gwl_style)
    if not style & ws_border:
        user32.SetWindowLongPtrW(handle, gwl_style, style | ws_border)
        # A pixel bigger each way: the border sits just off the screen, and
        # the view still fills it exactly.
        screen = window.screen()
        ratio = screen.devicePixelRatio()
        area = screen.geometry()
        user32.SetWindowPos(
            handle,
            None,
            round(area.x() * ratio) - 1,
            round(area.y() * ratio) - 1,
            round(area.width() * ratio) + 2,
            round(area.height() * ratio) + 2,
            flags,
        )
    # Windows 11 rounds a bordered window's corners, showing the desktop
    # through them; Qt resets this, so it is set every time.
    corner_preference, do_not_round = 33, ctypes.c_int(1)
    ctypes.WinDLL("dwmapi").DwmSetWindowAttribute(
        ctypes.c_void_p(handle),
        corner_preference,
        ctypes.byref(do_not_round),
        ctypes.sizeof(do_not_round),
    )
