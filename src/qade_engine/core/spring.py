# SPDX-License-Identifier: GPL-3.0-or-later
"""Critically damped springs: smooth follow motion with no overshoot."""


def spring_step(
    value: float, velocity: float, target: float, frequency: float, dt: float
) -> tuple[float, float]:
    """Advances a critically damped spring by one step.

    It eases out of rest and into the target without overshooting, and keeps
    its velocity when the target moves, so retargeting mid-motion stays smooth.

    Args:
        value: Current value.
        velocity: Current rate of change, per second.
        target: Where the value is heading.
        frequency: Stiffness in rad/s. It settles in about ``5 / frequency``
            seconds.
        dt: Step length in seconds. Stable while ``frequency * dt < 1``.

    Returns:
        The new value and velocity.
    """
    velocity += (
        frequency * frequency * (target - value) - 2 * frequency * velocity
    ) * dt
    return value + velocity * dt, velocity
