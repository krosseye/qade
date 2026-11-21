# SPDX-License-Identifier: GPL-3.0-or-later
"""
Build one QADE game, or the launcher with every game it lists, with PyInstaller.

uv run build.py                   # the launcher and all its games
uv run build.py grizzly_depths    # any one game
"""

import argparse
import importlib
import os
import platform
from importlib.metadata import version

import PyInstaller.__main__

from qade_engine import GameDefinition
from qade_engine.diagnostics import sys_architecture

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.join(PROJECT_DIR, "src")

PLATFORM = platform.system().lower()
ARCHITECTURE = sys_architecture()
TARGET = f"{PLATFORM}-{ARCHITECTURE}"

BUILD_DIR = os.path.join(PROJECT_DIR, "build")
DIST_DIR = os.path.join(BUILD_DIR, "bin", TARGET)
DEFAULT_PACKAGE = "qade_launcher"


def definitions(package: str) -> list[GameDefinition]:
    """What the target runs: its game, or the launcher and its games."""
    module = importlib.import_module(package)
    if hasattr(module, "LAUNCHER"):
        return [module.LAUNCHER, *module.GAMES]
    if hasattr(module, "GAME"):
        return [module.GAME]
    raise SystemExit(f"{package} defines neither GAME nor LAUNCHER")


def resource_dir(package: str) -> str:
    return os.path.join(SOURCE_ROOT, *package.split("."), "resources")


def resource_data(packages: list[str]) -> list[str]:
    """``--add-data`` arguments for each package's resources folder, if it
    has one, placed where ``resource_path`` looks."""
    arguments = []
    for package in packages:
        folder = resource_dir(package)
        if os.path.isdir(folder):
            destination = os.path.join(*package.split("."), "resources")
            arguments += ["--add-data", f"{folder}{os.pathsep}{destination}"]
    return arguments


def icon(package: str) -> list[str]:
    """``--icon`` for the package's own icon, or nothing if it has none."""
    name = "icon.ico" if PLATFORM == "windows" else "icon.png"
    path = os.path.join(resource_dir(package), name)
    return ["--icon", path] if os.path.exists(path) else []


def executable_name(title: str) -> str:
    """The title in CamelCase, then version and platform: GrizzlyDepths-0.4.0-windows-x64."""
    words = "".join(c if c.isalnum() else " " for c in title).split()
    camel = "".join(word[:1].upper() + word[1:] for word in words)
    return f"{camel}-{version('qade')}-{TARGET}"


def build(package: str) -> None:
    entry = os.path.join(SOURCE_ROOT, *package.split("."), "__main__.py")
    if not os.path.exists(entry):
        raise SystemExit(f"{package} has no __main__.py to build from")
    games = definitions(package)
    packages = list(dict.fromkeys(game.info.package for game in games))
    name = executable_name(games[0].info.title)
    artifacts_dir = os.path.join(BUILD_DIR, "artifacts", TARGET, package)

    print(f"Building {name} with resources from: {', '.join(packages)}")
    PyInstaller.__main__.run(
        [
            entry,
            "--name",
            name,
            *icon(package),
            "--distpath",
            DIST_DIR,
            "--workpath",
            os.path.join(artifacts_dir, "work"),
            "--specpath",
            artifacts_dir,
            "--paths",
            SOURCE_ROOT,
            *resource_data(packages),
            "--collect-all",
            "sdl2dll",
            "--onefile",
            "--clean",
            "--noconfirm",
            "--windowed",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "package",
        nargs="?",
        default=DEFAULT_PACKAGE,
        help=f"game or launcher package to build (default: {DEFAULT_PACKAGE})",
    )
    build(parser.parse_args().package)


if __name__ == "__main__":
    main()
