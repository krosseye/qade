# SPDX-License-Identifier: GPL-3.0-or-later
"""Engine fundamentals with no Qt dependency: play field, geometry, springs, phase flow."""

from .field import PlayField
from .geometry import clamp, dist_sq, lerp
from .spring import spring_step
from .state_machine import Edge, Transition, TransitionStyle

__all__ = [
    "Edge",
    "PlayField",
    "Transition",
    "TransitionStyle",
    "clamp",
    "dist_sq",
    "lerp",
    "spring_step",
]
