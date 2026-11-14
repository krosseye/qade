# SPDX-License-Identifier: GPL-3.0-or-later
"""The interface theme: colours by role, and the interface font."""

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


def _rotate_hue(color: QColor, shift: float) -> QColor:
    """Rotates a colour's hue, keeping saturation, value and alpha. Greys are unchanged."""
    hue = color.hsvHueF()
    if hue < 0:
        return QColor(color)
    return QColor.fromHsvF(
        (hue + shift) % 1.0, color.hsvSaturationF(), color.valueF(), color.alphaF()
    )


@dataclass(frozen=True, slots=True)
class Theme:
    """Interface colours by role. Interface code picks a role, never a hue.

    Translucent variants come from ``with_alpha(role, Opacity.X)``, not new
    roles. The brand roles follow the system accent colour; the status roles
    stay fixed so their meaning never changes.

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
        """Copies the theme with its brand roles hue-shifted to match an accent.

        Each role keeps its saturation and brightness, so the design's contrast
        holds for any accent. Status roles are unchanged.

        Args:
            accent: The colour whose hue to adopt.

        Returns:
            The tinted theme, or this theme if ``accent`` is grey.
        """
        if accent.hsvHueF() < 0:
            return self
        shift = accent.hsvHueF() - self.accent.hsvHueF()
        return replace(
            self,
            accent=_rotate_hue(self.accent, shift),
            highlight=_rotate_hue(self.highlight, shift),
            text=_rotate_hue(self.text, shift),
            text_muted=_rotate_hue(self.text_muted, shift),
            surface=_rotate_hue(self.surface, shift),
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
