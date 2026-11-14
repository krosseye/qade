# SPDX-License-Identifier: GPL-3.0-or-later
"""System diagnostics, logged at startup to help with bug reports."""

from .system_info import log_system_info, sys_architecture

__all__ = ["log_system_info", "sys_architecture"]
