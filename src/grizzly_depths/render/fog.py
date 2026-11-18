# SPDX-License-Identifier: GPL-3.0-or-later
"""How far things fade into the dark."""

from ..config import VIEW_RADIUS


def fog_at(distance: float) -> float:
    """1 up close, 0 at the edge of sight."""
    return max(0.0, 1.0 - distance / VIEW_RADIUS)
