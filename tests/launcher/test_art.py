# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher cabinet art: caching, determinism and awkward titles."""

import random

import pytest
from PySide6.QtGui import QPainter
from support import blank_image

from qade_launcher import art


def test_art_is_cached_per_title_and_accent():
    assert art.marquee("A", "#ff0000") is art.marquee("A", "#ff0000")
    assert art.marquee("A", "#ff0000") is not art.marquee("A", "#00ff00")
    assert art.screen("A", "#ff0000") is not art.screen("B", "#ff0000")


def test_screen_art_is_the_same_every_run(monkeypatch):
    first = art.screen("Repeatable", "#336699").toImage()
    art.screen.cache_clear()

    random.seed(12345)
    second = art.screen("Repeatable", "#336699").toImage()
    assert first == second


@pytest.mark.parametrize(
    "title", ["", " ", "X", "Ünïcødé ★ 漢字", "W" * 300, "line\nbreak"]
)
def test_awkward_titles_still_make_art(title):
    for pixmap in (
        art.marquee(title, "#ffaa00"),
        art.screen(title, "#ffaa00"),
    ):
        assert not pixmap.isNull()


def test_titles_shrink_to_fit_and_stop_at_the_smallest_size():
    image = blank_image(10, 10)
    painter = QPainter(image)
    try:
        short = art._fitted_size(painter, "ZAP", 300, 46, 3)
        assert short == 46
        medium = art._fitted_size(painter, "GALAXY RUN", 300, 46, 3)
        assert 8 < medium < 46
        art._set_font(painter, medium, 3)
        assert painter.fontMetrics().horizontalAdvance("GALAXY RUN") <= 300
        art._set_font(painter, medium + 2, 3)
        assert painter.fontMetrics().horizontalAdvance("GALAXY RUN") > 300
        assert art._fitted_size(painter, "W" * 300, 300, 46, 3) == 8
        smallest = painter.fontMetrics().horizontalAdvance("W" * 300)
        art._set_font(painter, 8, 3)
        assert painter.fontMetrics().horizontalAdvance("W" * 300) == smallest
    finally:
        painter.end()
