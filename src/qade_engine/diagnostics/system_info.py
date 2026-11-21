# SPDX-License-Identifier: GPL-3.0-or-later
"""System diagnostics: environment, GPU and OpenGL, displays and packaging."""

from __future__ import annotations

import logging
import os
import platform
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from PySide6.QtCore import qVersion
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext

_log = logging.getLogger(__name__)

SystemInformationDictionary = dict[str, dict[str, str]]

# OpenGL glGetString enums.
_GL_RENDERER = 0x1F01
_GL_VERSION = 0x1F02

# Substrings found in renderer names of CPU-based OpenGL implementations.
_SOFTWARE_RENDERER_HINTS = (
    "llvmpipe",
    "softpipe",
    "lavapipe",
    "swrast",
    "software",
    "basic render",
    "gdi generic",
)

# Environment variables that change how Qt picks a platform or renderer.
_QT_ENV_OVERRIDES = (
    "QT_OPENGL",
    "QT_QUICK_BACKEND",
    "QSG_RHI_BACKEND",
    "QT_QPA_PLATFORM",
    "QT_ENABLE_HIGHDPI_SCALING",
    "QT_SCALE_FACTOR",
)


def sys_architecture() -> str:
    """The CPU architecture, as a short name.

    Returns:
        ``x64``, ``x86``, ``arm64`` or ``arm``, else the platform's own name.
    """
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x64"
    if machine in {"i386", "i486", "i586", "i686", "x86"}:
        return "x86"
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine.startswith("armv") or machine == "arm":
        return "arm"
    return machine


def _os_description() -> str:
    if platform.system() != "Windows":
        return f"{platform.system()} {platform.release()}"
    try:
        build = int(platform.version().rpartition(".")[2])
    except ValueError:
        return f"Windows {platform.release()}"
    # platform.release() reports "10" on Windows 11; build >= 22000 is the real marker.
    name = "Windows 11" if build >= 22000 else f"Windows {platform.release()}"
    return f"{name} (build {build})"


def _packaging() -> str:
    """How the game is being run: from source, PyInstaller, Nuitka or another freezer."""
    if "__compiled__" in globals():
        return "Nuitka"
    if hasattr(sys, "_MEIPASS"):
        return "PyInstaller"
    if getattr(sys, "frozen", False):
        return "frozen (other)"
    return "source"


def _gl_string(functions, enum: int) -> str:
    value = functions.glGetString(enum)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode(errors="replace")
    return str(value) if value else "unknown"


@contextmanager
def _temporary_gl_context() -> Iterator[QOpenGLContext | None]:
    """Yields a current offscreen OpenGL context, or None if one can't be made."""
    context = QOpenGLContext()
    if QGuiApplication.instance() is None or not context.create():
        yield None
        return

    surface = QOffscreenSurface()
    surface.create()
    made_current = context.makeCurrent(surface)
    try:
        yield context if made_current else None
    finally:
        if made_current:
            context.doneCurrent()
        surface.destroy()


def _probe_gpu() -> tuple[dict[str, str], bool] | None:
    """(GPU details, whether OpenGL runs on the CPU), or None without a context."""
    with _temporary_gl_context() as gl_context:
        if gl_context is None or (functions := gl_context.functions()) is None:
            return None

        renderer = _gl_string(functions, _GL_RENDERER)
        details = {
            "GPU Renderer": renderer,
            "GPU OpenGL Version": _gl_string(functions, _GL_VERSION),
            "GPU Module Type": QOpenGLContext.openGLModuleType().name,
        }
        is_software = any(hint in renderer.lower() for hint in _SOFTWARE_RENDERER_HINTS)
        return details, is_software


def _screen_details() -> dict[str, str]:
    primary = QGuiApplication.primaryScreen()
    return {
        f"Screen {i}": (
            f"{s.name()} {s.size().width()}x{s.size().height()} "
            f"@ {s.refreshRate():.0f}Hz, scale {s.devicePixelRatio():g}"
            + (" (primary)" if s == primary else "")
        )
        for i, s in enumerate(QGuiApplication.screens())
    }


def collect_system_info(
    requested_hardware_mode: bool = True,
) -> SystemInformationDictionary:
    """Collects diagnostics.

    Args:
        requested_hardware_mode: Whether OpenGL rendering was requested. When
            False the GPU is not probed, as software rendering is the way out
            of a broken driver.

    Returns:
        Labelled values, grouped into "Software", "Hardware" and "State".
    """
    app = QGuiApplication.instance()

    software = {
        "Operating System": _os_description(),
        "Python Version": f"{platform.python_implementation()} {platform.python_version()} ({platform.architecture()[0]})",
        "Qt Version": qVersion(),
    }

    hardware = {
        "CPU Architecture": sys_architecture(),
        "Logical CPU Cores": str(os.cpu_count() or "unknown"),
    }

    gpu_probe = None
    if not requested_hardware_mode:
        hardware["GPU Status"] = "Not probed (software renderer requested)"
    else:
        try:
            gpu_probe = _probe_gpu()
        except (RuntimeError, TypeError) as exc:
            hardware["GPU Status"] = f"Error probing context: {type(exc).__name__}"
        else:
            if gpu_probe is None:
                hardware["GPU Status"] = (
                    "Unavailable (could not access or create OpenGL context)"
                )
            else:
                hardware.update(gpu_probe[0])

    if app is not None:
        hardware.update(_screen_details())

    if not requested_hardware_mode:
        effective = "CPU (software rasterizer)"
    elif gpu_probe is None:
        effective = "unknown (no OpenGL context available)"
    elif gpu_probe[1]:
        effective = "CPU (software OpenGL fallback)"
    else:
        effective = "GPU (hardware accelerated)"

    overrides = [f"{k}={os.environ[k]}" for k in _QT_ENV_OVERRIDES if k in os.environ]
    state = {
        "Requested Renderer": (
            "hardware (QOpenGLWidget)"
            if requested_hardware_mode
            else "software (QWidget raster)"
        ),
        "Effective Renderer": effective,
        "Packaging": _packaging(),
        "Executable": sys.executable,
        "Qt Platform Plugin": QGuiApplication.platformName()
        if app is not None
        else "no QGuiApplication",
        "Qt Env Overrides": ", ".join(overrides) or "none",
        "Date/Time": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
    }

    return {"Software": software, "Hardware": hardware, "State": state}


def log_system_info(use_hardware: bool = True) -> None:
    """Collects diagnostics and logs them as one record, a line per value.

    Args:
        use_hardware: Whether OpenGL rendering was requested.
    """
    lines = ["system info"]
    for section, items in collect_system_info(use_hardware).items():
        lines.append(f"  [{section}]")
        lines += (f"    {label}: {value}" for label, value in items.items())
    _log.info("\n".join(lines))
