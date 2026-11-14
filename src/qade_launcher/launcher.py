# SPDX-License-Identifier: GPL-3.0-or-later
"""The launcher: an aisle of arcade cabinets, one per game.

It is a plain ``App``, not an ``ArcadeGame``. Left and right walk along the
aisle; confirming steps up to the cabinet and launches its game. Quitting the
game brings the host back here (the launcher is its ``home``), standing at the
same cabinet.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPen

from qade_engine import Frame, GameDefinition, Services
from qade_engine.audio import SoundBus, open_bus
from qade_engine.core import clamp, lerp, spring_step
from qade_engine.graphics import (
    BLACK,
    Camera,
    Pose,
    blend,
    current_theme,
    draw_centered,
    make_font,
    with_alpha,
)
from qade_engine.input import UIAction
from qade_engine.ui import draw_terminal_frame

from . import sounds
from .aisle import draw_aisle
from .cabinet import SCREEN_CENTER
from .controls import Action, input_map
from .units import UNIT_SPACING, build_units, side

CANVAS_SIZE = (800, 600)
TICK_HZ = 64

EYE_HEIGHT = 1.6
VIEW_DISTANCE = 4.0  # the camera stands this far before the selected unit
VIEW_OFFSET_X = 0.45  # and this far across the aisle from it
VIEW_YAW = 14.0  # degrees turned towards it, which also turns away from the last
LAUNCH_DISTANCE = 0.9  # how far from the screen launching stops

WALK_STIFFNESS = 9.0  # spring frequency (rad/s): settles in about half a second
REPEAT_DELAY = 0.35  # holding a direction walks on after this long...
REPEAT_INTERVAL = 0.2  # ...and then this often
LAUNCH_TIME = 0.8  # step up to the cabinet and fade out
LAUNCH_FADE_START = 0.45  # fraction of the launch before the fade begins
FADE_IN_TIME = 0.45


@dataclass
class LauncherMemory:
    """What survives leaving the launcher for a game and coming back."""

    selected: int = 0


class Launcher:
    """Walk the aisle, launch a cabinet's game. Implements the host's ``App``."""

    canvas_size = CANVAS_SIZE
    tick_hz = TICK_HZ

    def __init__(
        self,
        services: Services,
        games: Sequence[GameDefinition],
        memory: LauncherMemory | None = None,
    ):
        self.services = services
        self.games = list(games)
        self.memory = memory or LauncherMemory()
        self.units = build_units(self.games)
        self.input_map = input_map()

        self.selected = clamp(self.memory.selected, 0, max(len(self.games) - 1, 0))
        self.pose = self._rest_pose(self.selected)
        self._velocity: tuple[float, ...] = (0.0, 0.0, 0.0)
        self.fade = 1.0
        self._previous = (self.pose, self.fade)

        self._held: Action | None = None
        self._repeat_timer = 0.0
        self._launch_from: Pose | None = None
        self._launch_progress = 0.0
        self.sounds: SoundBus | None = None

    def _rest_pose(self, index: int) -> Pose:
        return Pose(
            x=-side(index) * VIEW_OFFSET_X,
            y=EYE_HEIGHT,
            z=index * UNIT_SPACING - VIEW_DISTANCE,
            yaw=side(index) * VIEW_YAW,
        )

    def _launch_pose(self, index: int) -> Pose:
        """Square in front of the cabinet's screen."""
        cabinet = self.units[index].cabinet
        _, screen_y, screen_z = SCREEN_CENTER
        x, _, z = cabinet.world(0.0, screen_y, screen_z - LAUNCH_DISTANCE)
        return Pose(x, screen_y, z, cabinet.yaw)

    @property
    def launching(self) -> bool:
        return self._launch_from is not None

    def start(self) -> None:
        """Build any cabinet art not already cached, before the first frame
        needs it, so the walk never stutters on a first sight. Likewise the
        sounds."""
        for unit in self.units:
            for build in unit.cabinet.art.values():
                build()
        if self.services.settings.sound_effects:
            self.sounds = open_bus(sounds.register)

    def stop(self) -> None:
        if self.sounds is not None:
            self.sounds.close()
            self.sounds = None

    def suspend(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def _play(self, name: str, step: int | None = None) -> None:
        if self.sounds is not None:
            self.sounds.play(name, step=step)

    def on_action(self, action: str) -> None:
        if self.launching or not self.games:
            return
        match action:
            case Action.PREVIOUS | Action.NEXT:
                self._held = Action(action)
                self._repeat_timer = REPEAT_DELAY
                self._walk(action, pressed=True)
            case UIAction.CONFIRM:
                self._launch_from = self.pose
                self._launch_progress = 0.0
                self._play(sounds.COIN)
                self._play(sounds.POWER_UP)

    def _walk(self, action: str, pressed: bool = False) -> None:
        step = -1 if action == Action.PREVIOUS else 1
        selected = clamp(self.selected + step, 0, len(self.games) - 1)
        if selected == self.selected:
            if pressed:
                self._play(sounds.END)
            return
        self.selected = self.memory.selected = selected
        self._play(sounds.SELECT, step=selected % len(sounds.UNIT_SEMITONES))

    def step(self, dt: float) -> None:
        self._previous = (self.pose, self.fade)
        if self._launch_from is not None:
            self._step_launch(dt)
            return

        self.fade = max(0.0, self.fade - dt / FADE_IN_TIME)
        if self._held is not None:
            if self.services.actions.is_pressed(self._held):
                self._repeat_timer -= dt
                if self._repeat_timer <= 0:
                    self._repeat_timer += REPEAT_INTERVAL
                    self._walk(self._held)
            else:
                self._held = None

        target = self._rest_pose(self.selected)
        (x, vx), (z, vz), (yaw, vyaw) = (
            spring_step(now, velocity, end, WALK_STIFFNESS, dt)
            for now, end, velocity in zip(
                (self.pose.x, self.pose.z, self.pose.yaw),
                (target.x, target.z, target.yaw),
                self._velocity,
            )
        )
        self._velocity = (vx, vz, vyaw)
        self.pose = Pose(x, target.y, z, yaw)

    def _step_launch(self, dt: float) -> None:
        assert self._launch_from is not None
        self._launch_progress = min(1.0, self._launch_progress + dt / LAUNCH_TIME)
        progress = self._launch_progress
        eased = progress * progress * (3 - 2 * progress)
        self.pose = self._launch_from.lerp(self._launch_pose(self.selected), eased)
        fade = (progress - LAUNCH_FADE_START) / (1 - LAUNCH_FADE_START)
        self.fade = max(self.fade, clamp(fade, 0.0, 1.0))
        game = self.units[self.selected].game
        if progress >= 1.0 and game is not None:
            self.services.launch(game)
            self._launch_from = None
            self._launch_progress = 0.0

    def _focus(self, pose: Pose) -> float:
        """Which unit the camera is at, as a continuous index."""
        if self.launching:
            return float(self.selected)
        return (pose.z + VIEW_DISTANCE) / UNIT_SPACING

    def _glow(self, focus: float) -> QColor:
        """The aisle's tint: the accent of the game in focus, blended between units."""
        last = max(len(self.games) - 1, 0)
        focus = clamp(focus, 0.0, float(last))
        low = int(focus)
        high = min(low + 1, last)
        return blend(
            self.units[low].cabinet.accent, self.units[high].cabinet.accent, focus - low
        )

    def draw(self, frame: Frame) -> None:
        painter, view = frame.painter, frame.view
        previous_pose, previous_fade = self._previous
        blend_amount = frame.alpha
        pose = previous_pose.lerp(self.pose, blend_amount)
        fade = lerp(previous_fade, self.fade, blend_amount)

        camera = Camera(
            pose,
            focal=view.height * 0.8,
            center_x=view.width / 2,
            horizon=view.height * 0.44,
        )
        focus = self._focus(pose)
        last_z = (len(self.units) - 1) * UNIT_SPACING
        draw_aisle(painter, camera, -VIEW_DISTANCE - 4, last_z + 4, self._glow(focus))

        by_depth = sorted(
            (
                (camera.depth((unit.cabinet.x, 0, unit.cabinet.z)), index, unit)
                for index, unit in enumerate(self.units)
            ),
            key=lambda item: -item[0],
        )
        visible = [(index, unit) for depth, index, unit in by_depth if depth > -1.0]
        brightness = {
            index: max(0.0, 1.0 - abs(index - focus) * 1.25) if unit.game else 0.0
            for index, unit in visible
        }
        for index, unit in visible:
            unit.cabinet.draw_floor_glow(painter, camera, brightness[index])
        for index, unit in visible:
            unit.cabinet.draw(painter, camera, brightness[index])

        overlay = 1.0 - min(1.0, self._launch_progress * 2.5) if self.launching else 1.0
        if overlay > 0:
            painter.save()
            painter.setOpacity(overlay)
            self._draw_overlay(frame, brightness.get(self.selected, 0.0))
            painter.restore()

        if fade > 0.001:
            painter.fillRect(
                QRectF(0, 0, view.width, view.height),
                with_alpha(BLACK, int(255 * fade)),
            )

    def _draw_overlay(self, frame: Frame, arrival: float) -> None:
        """The unit counter and the selected game's name plate."""
        theme = current_theme()
        painter, view = frame.painter, frame.view
        unit = self.units[self.selected]
        info = unit.game.info if unit.game else None
        if info is None:
            return

        width, height = 560.0, 112.0
        x, y = (view.width - width) / 2, view.height - height - 16
        header = draw_terminal_frame(
            painter,
            x,
            y,
            width,
            height,
            f"UNIT {self.selected + 1:02d} / {len(self.games):02d}",
        )
        make_font(painter, 24, spacing=6)
        title_color = blend(theme.text_muted, unit.cabinet.accent, arrival)
        painter.setPen(QPen(with_alpha(title_color, int(110 + 145 * arrival))))
        draw_centered(painter, info.title.upper(), view.width, y + header + 34)

        make_font(painter, 9, spacing=1.5)
        painter.setPen(QPen(theme.text_muted))
        draw_centered(painter, info.description.upper(), view.width, y + header + 54)

        make_font(painter, 10, spacing=1.5)
        painter.setPen(QPen(theme.highlight))
        draw_centered(
            painter,
            "[ < > ] WALK     [ ENTER ] PLAY     [ ESC ] EXIT",
            view.width,
            y + height - 12,
        )
