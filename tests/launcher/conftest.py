# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixtures for the launcher tests."""

import pytest
from launcher_rig import Rig


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch) -> Rig:
    return Rig(monkeypatch)
