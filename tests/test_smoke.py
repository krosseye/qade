# SPDX-License-Identifier: GPL-3.0-or-later
"""Placeholder until the real suite lands: the engine and its Qt modules import."""


def test_engine_imports() -> None:
    import qade_engine

    assert qade_engine.ArcadeGame is not None
