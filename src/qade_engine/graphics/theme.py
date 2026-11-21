# SPDX-License-Identifier: GPL-3.0-or-later
"""The interface theme: colours by role, and the interface font."""

import math
from dataclasses import dataclass, replace
from functools import cache

from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPalette

from .palette import CYAN, GREEN, ORANGE, RED, YELLOW

FONT_FAMILIES: list[str] = [
    "Consolas",
    "Courier New",
    "Courier",
    "DejaVu Sans Mono",
    "monospace",
]


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _encode(channel: float) -> float:
    if channel <= 0.0031308:
        return 12.92 * channel
    return 1.055 * channel ** (1 / 2.4) - 0.055


def oklch(color: QColor) -> tuple[float, float, float]:
    """A colour's OKLCH lightness (0-1), chroma (0-~0.37) and hue (degrees)."""
    r, g, b = (_linear(c) for c in (color.redF(), color.greenF(), color.blueF()))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return lightness, math.hypot(a, b_), math.degrees(math.atan2(b_, a)) % 360


def _oklch_to_rgb(lightness: float, chroma: float, hue: float) -> list[float]:
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return [
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    ]


def from_oklch(
    lightness: float, chroma: float, hue: float, alpha: float = 1.0
) -> QColor:
    """The colour at an OKLCH point, losing chroma until a screen can show it."""
    low, high = 0.0, chroma
    rgb = _oklch_to_rgb(lightness, chroma, hue)
    if not all(-1e-4 <= c <= 1 + 1e-4 for c in rgb):
        for _ in range(20):
            mid = (low + high) / 2
            if all(-1e-4 <= c <= 1 + 1e-4 for c in _oklch_to_rgb(lightness, mid, hue)):
                low = mid
            else:
                high = mid
        rgb = _oklch_to_rgb(lightness, low, hue)
    r, g, b = (min(1.0, max(0.0, _encode(min(1.0, max(0.0, c))))) for c in rgb)
    return QColor.fromRgbF(r, g, b, alpha)


def _with_hue(color: QColor, hue: float) -> QColor:
    """The colour at another hue, at the same OKLCH lightness and chroma."""
    lightness, chroma, _ = oklch(color)
    return from_oklch(lightness, chroma, hue, color.alphaF())


def _hue_gap(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


GREY_CHROMA = 0.03
MIN_HIGHLIGHT_GAP = 50.0


@dataclass(frozen=True, slots=True)
class Theme:
    """Interface colours by role. Interface code picks a role, never a hue.

    Translucent variants come from ``with_alpha(role, Opacity.X)``, not new
    roles. The brand roles follow the running app's accent, or the system's;
    the status roles stay fixed so their meaning never changes.

    Attributes:
        accent: Brand colour: titles, borders, brackets, main readouts.
        highlight: Draws the eye: records, prompts, calls to action.
        text: Body text.
        text_muted: Labels and secondary information.
        surface: Panel and backdrop fills, used with an ``Opacity`` level.
        success: Healthy status.
        warning: Degraded status.
        danger: Failure and critical messages.
    """

    accent: QColor
    highlight: QColor
    text: QColor
    text_muted: QColor
    surface: QColor
    success: QColor
    warning: QColor
    danger: QColor

    def with_accent(self, accent: QColor) -> "Theme":
        """Copies the theme with its brand roles in an accent's hue.

        Hues are swapped in OKLCH, where each role keeps its lightness and
        chroma, so every accent looks as bright and reads as clearly against
        the surface as the default. The highlight keeps its own hue unless the
        accent is too close to it, when it takes the default accent's instead.
        Status roles are unchanged.

        Args:
            accent: The colour whose hue to adopt.

        Returns:
            The tinted theme, or this theme if ``accent`` is grey.
        """
        _, chroma, hue = oklch(accent)
        if chroma < GREY_CHROMA:
            return self
        highlight_hue = oklch(self.highlight)[2]
        if _hue_gap(hue, highlight_hue) < MIN_HIGHLIGHT_GAP:
            highlight_hue = oklch(self.accent)[2]
        return replace(
            self,
            accent=_with_hue(self.accent, hue),
            highlight=_with_hue(self.highlight, highlight_hue),
            text=_with_hue(self.text, hue),
            text_muted=_with_hue(self.text_muted, hue),
            surface=_with_hue(self.surface, hue),
        )


DEFAULT_THEME: Theme = Theme(
    accent=CYAN,
    highlight=YELLOW,
    text=QColor(180, 230, 255),
    text_muted=QColor(140, 180, 210),
    surface=QColor(10, 20, 35),
    success=GREEN,
    warning=ORANGE,
    danger=RED,
)

_active_theme: Theme = DEFAULT_THEME


def current_theme() -> Theme:
    """The theme interface code should draw with."""
    return _active_theme


def system_accent_color() -> QColor:
    """The platform's accent colour, or its highlight colour where Qt has no accent.

    Returns:
        The colour.
    """
    color_role = getattr(QPalette.ColorRole, "Accent", QPalette.ColorRole.Highlight)
    return QGuiApplication.palette().color(color_role)


def apply_accent(accent: QColor | None = None) -> Theme:
    """Activates the default theme, tinted to an accent colour.

    Args:
        accent: The accent to adopt. None uses the system's, which needs a
            running QGuiApplication.

    Returns:
        The newly active theme.
    """
    global _active_theme
    _active_theme = DEFAULT_THEME.with_accent(accent or system_accent_color())
    return _active_theme


@cache
def _font(size: float, bold: bool, spacing: float) -> QFont:
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPixelSize(max(1, round(size * 4 / 3)))
    font.setBold(bold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def make_font(
    painter: QPainter, size: float, bold: bool = True, spacing: float = 0.0
) -> QFont:
    """Sets the interface font on a painter.

    The font comes from these arguments alone: nothing carries over from the
    painter's previous font.

    Args:
        painter: The painter to update.
        size: Size in points, at a fixed 96 per inch.
        bold: Whether the font is bold.
        spacing: Letter spacing in pixels.

    Returns:
        A copy of the font, free to modify. Qt fonts are copy-on-write, so it
        costs next to nothing until changed.
    """
    font = _font(size, bold, spacing)
    painter.setFont(font)
    return QFont(font)
