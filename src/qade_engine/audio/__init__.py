# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthesised sound effects, and the bus that plays them.

In an ``ArcadeGame``, register sounds in ``register_sounds`` and play them
with ``play_sound`` and ``stop_sound``, which do nothing when sound is off.

Example:
    ```python
    def register_sounds(self, bus):
        bus.register("fire", presets.laser(), voices=3, gap=0.05)
        bus.register("hum", Sfx("tri", 880, decay=0, loop=True))

    def step_playing(self, dt):
        self.play_sound("fire")
        self.play_sound("hum")  # a loop: safe to call every step
    ```
"""

from . import presets
from .bus import SoundBus, open_bus
from .synth import Sfx

__all__ = ["Sfx", "SoundBus", "open_bus", "presets"]
