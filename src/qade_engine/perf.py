# SPDX-License-Identifier: GPL-3.0-or-later
"""Frame-rate and update-rate measurements for the HUD."""

from dataclasses import dataclass
from time import perf_counter


class FrameStats:
    """Event rate and interval statistics, refreshed once per window.

    Attributes:
        rate: Events per second.
        avg_ms: Mean interval between events, in milliseconds.
        worst_ms: Longest single interval in the window, so one hitch isn't
            hidden by a healthy average.
    """

    def __init__(self, window=0.5, clock=perf_counter):
        """Creates the statistics.

        Args:
            window: Seconds per window.
            clock: Returns seconds.
        """
        self._clock = clock
        self._window = window
        self._last = None
        self._window_start = 0.0
        self._count = 0
        self._worst = 0.0
        self.rate = 0.0
        self.avg_ms = 0.0
        self.worst_ms = 0.0

    def tick(self, count=1):
        """Records events. The first call only sets the starting time.

        Args:
            count: Events since the last call. Pass 0 to let the window
                advance while nothing happened, so the rate drops to 0.
        """
        now = self._clock()
        if self._last is None:
            self._last = self._window_start = now
            return

        dt = now - self._last
        self._last = now
        if count > 0:
            self._worst = max(self._worst, dt / count)
            self._count += count

        elapsed = now - self._window_start
        if elapsed >= self._window:
            self.rate = self._count / elapsed
            self.avg_ms = elapsed / self._count * 1000.0 if self._count else 0.0
            self.worst_ms = self._worst * 1000.0
            self._window_start = now
            self._count = 0
            self._worst = 0.0


@dataclass
class PerfStats:
    """Measurements written by the host and read by the HUD.

    Attributes:
        fps: Paints per second.
        frame_ms: Mean time between paints.
        worst_ms: Longest gap between paints in the last window.
        ups: Fixed simulation steps actually run per second.
        paint_ms: Smoothed time spent painting.
        target_fps: The display's refresh rate.
        target_ups: The running app's step rate.
        show_details: Show the extra HUD rows, toggled with F3.
    """

    fps: float = 0.0
    frame_ms: float = 0.0
    worst_ms: float = 0.0
    ups: float = 0.0
    paint_ms: float = 0.0
    target_fps: float = 60.0
    target_ups: float = 64.0
    show_details: bool = False

    def record_paint_time(self, ms: float) -> None:
        """Folds one paint's duration into ``paint_ms``, an exponential moving average.

        Args:
            ms: The paint's duration in milliseconds.
        """
        if self.paint_ms == 0.0:
            self.paint_ms = ms
        else:
            self.paint_ms += 0.1 * (ms - self.paint_ms)
