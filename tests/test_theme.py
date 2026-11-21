# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from PySide6.QtGui import QColor

from qade_engine.graphics.theme import DEFAULT_THEME, from_oklch, oklch

HUES = range(0, 360, 10)


def luminance(color: QColor) -> float:
    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in (color.redF(), color.greenF(), color.blueF()))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def hue_gap(a: QColor, b: QColor) -> float:
    return abs((oklch(a)[2] - oklch(b)[2] + 180) % 360 - 180)


def contrast(a: QColor, b: QColor) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("name", ["#00dcff", "#ffd732", "#9678ff", "#0a1423"])
def test_oklch_round_trips(name):
    assert from_oklch(*oklch(QColor(name))).name() == name


def test_colours_a_screen_cannot_show_keep_lightness_and_hue():
    lightness, _, hue = oklch(from_oklch(0.8, 0.4, 300))
    assert lightness == pytest.approx(0.8, abs=0.01)
    assert hue == pytest.approx(300, abs=2)


@pytest.mark.parametrize("hue", HUES)
def test_every_accent_stays_readable_on_its_surface(hue):
    accent = from_oklch(0.6, 0.2, hue)
    theme = DEFAULT_THEME.with_accent(accent)
    assert hue_gap(theme.accent, accent) <= 3
    assert contrast(theme.text, theme.surface) >= 7
    for role in (theme.accent, theme.highlight, theme.text_muted):
        assert contrast(role, theme.surface) >= 4.5


@pytest.mark.parametrize("hue", HUES)
def test_the_highlight_stands_apart_from_the_accent(hue):
    theme = DEFAULT_THEME.with_accent(from_oklch(0.6, 0.2, hue))
    assert hue_gap(theme.highlight, theme.accent) >= 50


def test_a_grey_accent_leaves_the_theme_alone():
    assert DEFAULT_THEME.with_accent(QColor(128, 128, 128)) is DEFAULT_THEME
