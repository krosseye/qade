# SPDX-License-Identifier: GPL-3.0-or-later
"""Locating a game package's bundled files."""

from importlib.resources import files
from pathlib import Path


def resource_path(package: str, name: str) -> Path:
    """The absolute path of a file in a package's ``resources`` folder.

    Works from source and from a PyInstaller bundle, as long as the build adds
    the package's ``resources`` folder at the same relative location.

    Args:
        package: The package's import name.
        name: The file's name.

    Returns:
        The path to ``<package>/resources/<name>``.
    """
    return Path(str(files(package).joinpath("resources", name)))
