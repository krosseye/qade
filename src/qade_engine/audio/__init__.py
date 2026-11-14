# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthesised sound effects, and the bus that plays them.

Example:
    ```python
    bus.register("fire", presets.laser(), voices=3, gap=0.05)
    bus.register("hum", Sfx("tri", 880, decay=0, loop=True))
    bus.play("fire")
    bus.play("hum")  # safe to call every step
    bus.stop("hum")
    ```
"""

from . import presets
from .bus import SoundBus, open_bus
from .synth import Sfx

__all__ = ["Sfx", "SoundBus", "open_bus", "presets"]
