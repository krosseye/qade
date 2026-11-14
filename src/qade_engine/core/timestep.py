# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed-rate simulation steps from an irregular real-time clock."""

import math


class FixedTimestep:
    """Turns irregular real elapsed time into a whole number of fixed steps.

    Leftover time carries over to the next call, so the simulation averages
    exactly ``1 / step`` steps per second however the caller's timer jitters.

    Attributes:
        step: Length of one step, in seconds.
    """

    def __init__(self, step: float) -> None:
        """Creates the timestep with nothing accumulated.

        Args:
            step: Length of one step, in seconds.
        """
        self.step = step
        self._accumulated = 0.0

    def advance(self, elapsed: float) -> int:
        """Adds real elapsed time.

        Args:
            elapsed: Real seconds since the last call. Zero, negative and
                non-finite values add nothing, so one bad clock reading
                can't poison every later step.

        Returns:
            How many steps are now due.
        """
        if not 0.0 < elapsed < math.inf:
            return 0
        self._accumulated += elapsed
        steps = int(self._accumulated // self.step)
        self._accumulated %= self.step
        return steps

    @property
    def alpha(self) -> float:
        """How far the leftover time is into the next step, from 0 to 1.

        Drawing can blend the previous and current step by this much, so
        motion stays smooth when the display refreshes faster than the steps.
        """
        return self._accumulated / self.step
