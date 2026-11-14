# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing for games: fixed palette, theme roles, particles and a 3D camera."""

from .camera import NEAR, Camera, Point3, Pose
from .palette import (
    BLACK,
    CYAN,
    GREEN,
    GREY,
    ORANGE,
    RED,
    WHITE,
    YELLOW,
    Opacity,
    blend,
    with_alpha,
)
from .particles import Burst, ParticleEffect, ParticleSystem, Shape
from .primitives import draw_centered, draw_corner_brackets, hairline
from .theme import current_theme, make_font

__all__ = [
    "BLACK",
    "CYAN",
    "GREEN",
    "GREY",
    "NEAR",
    "ORANGE",
    "RED",
    "WHITE",
    "YELLOW",
    "Burst",
    "Camera",
    "Opacity",
    "ParticleEffect",
    "ParticleSystem",
    "Point3",
    "Pose",
    "Shape",
    "blend",
    "current_theme",
    "draw_centered",
    "draw_corner_brackets",
    "hairline",
    "make_font",
    "with_alpha",
]
