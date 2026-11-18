# SPDX-License-Identifier: GPL-3.0-or-later
"""Grizzly Depths: find the way out of the maze before the bear finds you."""

import random
from math import atan2, degrees, hypot

from PySide6.QtCore import QRectF
from PySide6.QtTextToSpeech import QVoice

from qade_engine import ArcadeGame, Frame, Phase
from qade_engine.audio import SoundBus
from qade_engine.core import clamp, lerp, spring_step
from qade_engine.graphics import (
    BLACK,
    RED,
    Camera,
    Pose,
    current_theme,
    with_alpha,
)
from qade_engine.input import InputMap
from qade_engine.ui import HUD_MARGIN, HudRow

from . import INFO, config, controls, music, sounds
from .bear import Mood
from .controls import Action
from .level import Level, build_level
from .maze import DIRECTIONS, opposite
from .render import (
    draw_attunement,
    draw_banner,
    draw_compass,
    draw_crystal_prompt,
    draw_dungeon,
    draw_status,
    draw_vignette,
)

DEATH_FLASH_TIME = 0.6
COMPASS_WIDTH = 340
CAUGHT_DISTANCE = 1.15

ViewState = tuple[float, float, float, float, float]  # camera x, z, yaw; bear x, z


class GrizzlyDepths(ArcadeGame):
    INFO = INFO
    CANVAS_SIZE = (config.CANVAS_WIDTH, config.CANVAS_HEIGHT)
    MUSIC = music.SONG
    IDLE_STAR_VELOCITY = (0.0, -160.0)

    TRANSMISSION_TITLE = "SCRATCHED INTO THE CAVE WALL"
    STANDBY_MESSAGE = "SOMETHING STIRS BELOW"
    STANDBY_PROMPT = "[ PRESS ANY KEY TO DESCEND ]"
    INTRO_LINES = (
        "YOU WAKE IN THE DARK BENEATH THE MOUNTAIN.",
        "THE TUNNELS SHIFT. NO MAP WILL SAVE YOU.",
        "SOMETHING LARGE SHARES THESE HALLS.",
        "THE BEAST IS HUNGRY, AND HAS YOUR SCENT.",
        "FIND AND WAKE THE CRYSTAL TO GO DEEPER.",
        "YOU WILL BE HEARD. DO NOT STOP MOVING.",
    )
    INTRO_HIGHLIGHTS = ("HUNGRY", "DO NOT STOP MOVING")
    INTRO_PROMPT = STANDBY_PROMPT
    GAME_OVER_TITLE = "MAULED // THE BEAR CAUGHT YOU"
    GAME_OVER_PROMPT = "[ PRESS ANY KEY TO WAKE AGAIN ]"
    HUD_TITLE = "SURVIVOR"
    VOICE_RATE = -0.2
    VOICE_GENDER = QVoice.Gender.Male
    GAME_OVER_DELAY = 1.4
    NEVER_CONFIRM = controls.MOVEMENT_KEYS
    STARS_IN_PLAY = False

    def register_sounds(self, bus: SoundBus) -> None:
        sounds.register(bus)

    def build_input_map(self) -> InputMap:
        return controls.input_map()

    def setup(self) -> None:
        self.rng = random.Random()

    def reset(self) -> None:
        self._start_level(1)

    def _start_level(self, number: int) -> None:
        self.level: Level = build_level(number, self.rng)
        self.cell = self.level.start
        self.facing = self.level.facing
        self.cooldown = 0.0
        self._buffered: Action | None = None
        self.level_time = 0.0
        self.heart_timer = 0.0
        self.approach: int | None = None
        self.heartbeats = 0
        self.beacon_angle = 0.0
        self.charge = 0.0
        self.attuning = False
        self.tick_timer = 0.0
        self.descent: float | None = None
        self.death_time = 0.0
        self.caught_yaw: float | None = None
        self.caught_bear: tuple[float, float] | None = None

        self.camera_x, self.camera_z = self._player_position()
        self.camera_yaw = self.facing * 90.0
        self._velocity = (0.0, 0.0, 0.0)
        self._previous = self._view_state()

    def _buffer_taps(self) -> None:
        """A tap between moves still counts: it is kept until the next move."""
        for action in (
            Action.FORWARD,
            Action.BACK,
            Action.TURN_LEFT,
            Action.TURN_RIGHT,
        ):
            if self.actions.was_pressed(action):
                self._buffered = action

    def _held(self) -> Action | None:
        """A held walk key repeats. Turns never do: one press, one quarter turn,
        so holding a turn a moment too long can't spin you round."""
        for action in (Action.FORWARD, Action.BACK):
            if self.actions.is_pressed(action):
                return action
        return None

    def step_playing(self, dt: float) -> None:
        self._previous = self._view_state()
        self._buffer_taps()
        self.level_time += dt
        self.beacon_angle += (2.0 + 10.0 * self.charge**2) * dt
        if self.descent is not None:
            self._step_descent(dt)
            self._follow_camera(dt)
            return

        self._move_player(dt)
        self._attune(dt)
        if self.charge >= 1.0:
            self.score += config.EXIT_SCORE * self.level.number
            self.descent = 0.0
            self.charge, self.attuning = 0.0, False
            self.stop_sound(sounds.HUM)
            self.play_sound(sounds.EXIT)
            return
        self._step_bear(dt)
        self._follow_camera(dt)
        if self._is_caught():
            self._turn_to_bear()
            self.play_sound(sounds.MAULED)
            self.died()

    def step_aftermath(self, dt: float) -> None:
        self._previous = self._view_state()
        self.death_time += dt
        self.beacon_angle += 2.0 * dt
        self._follow_camera(dt)

    def _move_player(self, dt: float) -> None:
        self.cooldown -= dt
        if self.cooldown > 0:
            return
        action = self._buffered or self._held()
        self._buffered = None
        match action:
            case Action.TURN_LEFT:
                self.facing -= 1
                self.cooldown = config.TURN_TIME
                self.play_sound(sounds.TURN)
            case Action.TURN_RIGHT:
                self.facing += 1
                self.cooldown = config.TURN_TIME
                self.play_sound(sounds.TURN)
            case Action.FORWARD | Action.BACK:
                direction = self.facing % 4
                if action is Action.BACK:
                    direction = opposite(direction)
                if self.level.maze.is_open(self.cell, direction):
                    self.cell = self.level.maze.step(self.cell, direction)
                    self.cooldown = config.STEP_TIME
                    self.play_sound(sounds.STEP)
                else:
                    self.cooldown = config.BUMP_TIME
                    self.play_sound(sounds.BUMP)
            case _:
                self.cooldown = 0.0

    def _attune(self, dt: float) -> None:
        """Charge the crystal while attune is held on it: it rings out as you
        start, then hums and ticks faster and higher as the charge fills. Let
        go and the charge drains away; step off and it is lost."""
        attuning = self.on_crystal and self.actions.is_pressed(Action.ATTUNE)
        if attuning and not self.attuning:
            self.play_sound(sounds.RESONATE)
            self.tick_timer = 0.0
        elif self.attuning and not attuning:
            self.stop_sound(sounds.HUM)
        if attuning:
            self.play_sound(sounds.HUM)
        self.attuning = attuning

        if not self.on_crystal:
            self.charge = 0.0
        elif attuning:
            fill = dt / config.attune_time(self.level.number)
            self.charge = min(1.0, self.charge + fill)
            self.tick_timer -= dt
            if self.tick_timer <= 0:
                self.tick_timer = sounds.tick_interval(self.charge)
                step = int(self.charge * len(sounds.TICK_SEMITONES))
                self.play_sound(sounds.TICK, step=step)
        else:
            self.charge = max(0.0, self.charge - dt / config.ATTUNE_FADE_TIME)

    def _step_descent(self, dt: float) -> None:
        """Fade out, swap in the next level at the darkest point, fade in."""
        assert self.descent is not None
        halfway = config.LEVEL_FADE_TIME / 2
        before = self.descent
        self.descent += dt
        if before < halfway <= self.descent:
            elapsed = self.descent
            self._start_level(self.level.number + 1)
            self.descent = elapsed
        elif self.descent >= config.LEVEL_FADE_TIME:
            self.descent = None

    def _follow_camera(self, dt: float) -> None:
        target_x, target_z = self._player_position()
        if self.caught_yaw is None:
            target_yaw, yaw_frequency = self.facing * 90.0, config.CAMERA_FREQUENCY
        else:
            target_yaw, yaw_frequency = self.caught_yaw, config.DEATH_TURN_FREQUENCY
        velocity_x, velocity_z, velocity_yaw = self._velocity
        frequency = config.CAMERA_FREQUENCY
        self.camera_x, velocity_x = spring_step(
            self.camera_x, velocity_x, target_x, frequency, dt
        )
        self.camera_z, velocity_z = spring_step(
            self.camera_z, velocity_z, target_z, frequency, dt
        )
        self.camera_yaw, velocity_yaw = spring_step(
            self.camera_yaw, velocity_yaw, target_yaw, yaw_frequency, dt
        )
        self._velocity = (velocity_x, velocity_z, velocity_yaw)

    def _step_bear(self, dt: float) -> None:
        """Move the bear, and let the player hear it: a distant roar when it
        wakes, a close one when it catches your scent, footsteps as it walks,
        and a heartbeat while it hunts you, quickening as it nears."""
        bear = self.level.bear
        was_awake, was_hunting, was_at = bear.awake, bear.hunting, bear.cell
        if self._touching_bear():
            bear.startle()
        bear.step(dt, self.cell, chiming=self.attuning)
        loudness = sounds.bear_volume(bear.path_distance)
        if bear.hunting and not was_hunting:
            self.play_sound(sounds.ROAR, vol=max(loudness, 0.6))
        elif bear.awake and not was_awake:
            self.play_sound(sounds.ROAR, vol=max(loudness, 0.25))
        elif bear.cell != was_at and loudness > 0:
            self.play_sound(sounds.BEAR_STEP, vol=loudness)
        self.approach = bear.approach(self.cell) if bear.hunting else None

        interval = (
            sounds.heartbeat_interval(bear.path_distance) if bear.hunting else None
        )
        self.heart_timer -= dt
        if interval is not None and self.heart_timer <= 0:
            self.heart_timer = interval
            self.play_sound(sounds.HEART, step=self.heartbeats % 2)
            self.heartbeats += 1

    @property
    def on_crystal(self) -> bool:
        """Standing on the exit, and not already on the way down."""
        return self.cell == self.level.exit and self.descent is None

    def _player_position(self) -> tuple[float, float]:
        return (self.cell[0] + 0.5, self.cell[1] + 0.5)

    def _is_caught(self) -> bool:
        return self.level.bear.mood is Mood.HUNTING and self._touching_bear()

    def _touching_bear(self) -> bool:
        bear_x, bear_z = self.level.bear.position
        player_x, player_z = self._player_position()
        return hypot(bear_x - player_x, bear_z - player_z) < config.CATCH_DISTANCE

    def _turn_to_bear(self) -> None:
        """Swing the view round to the bear, and stand it just in front."""
        player_x, player_z = self._player_position()
        bear_x, bear_z = self.level.bear.position
        dx, dz = bear_x - player_x, bear_z - player_z
        length = hypot(dx, dz)
        if length < 1e-3:  # caught dead centre: face the way it came in
            bear = self.level.bear
            dx = bear.came_from[0] - self.cell[0]
            dz = bear.came_from[1] - self.cell[1]
            if (dx, dz) == (0, 0):  # it never moved: you walked into it
                dx, dz = DIRECTIONS[self.facing % 4]
            length = hypot(dx, dz)
        heading = degrees(atan2(dx, dz))
        self.caught_yaw = (
            self.camera_yaw + (heading - self.camera_yaw + 180) % 360 - 180
        )
        self.caught_bear = (
            player_x + dx / length * CAUGHT_DISTANCE,
            player_z + dz / length * CAUGHT_DISTANCE,
        )

    def _bear_display(self) -> tuple[float, float]:
        return self.caught_bear or self.level.bear.position

    def _view_state(self) -> ViewState:
        bear_x, bear_z = self._bear_display()
        return (self.camera_x, self.camera_z, self.camera_yaw, bear_x, bear_z)

    def hud_rows(self) -> list[HudRow]:
        rows = super().hud_rows()
        rows.insert(
            2, HudRow("LEVEL", f"{self.level.number:02d}", current_theme().text)
        )
        return rows

    def draw_world(self, frame: Frame) -> None:
        painter, view = frame.painter, frame.view

        amount = frame.alpha
        x, z, yaw, bear_x, bear_z = (
            lerp(before, now, amount)
            for before, now in zip(self._previous, self._view_state())
        )
        camera = Camera(
            Pose(x, config.EYE_HEIGHT, z, yaw),
            focal=view.height * 0.85,
            center_x=view.width / 2,
            horizon=view.height / 2,
        )
        draw_dungeon(
            painter, camera, view.width, self.level, (bear_x, bear_z), self.beacon_angle
        )

        if self.phase is not Phase.GAME_OVER:
            side = None if self.approach is None else (self.approach - self.facing) % 4
            draw_vignette(painter, view.width, view.height, self._threat(), side)
            if self.on_crystal:
                flash = 0.0
                if self.attuning:
                    interval = sounds.tick_interval(self.charge)
                    flash = max(0.0, self.tick_timer) / interval
                draw_attunement(
                    painter,
                    view.width,
                    view.height,
                    self.charge,
                    self.beacon_angle,
                    flash,
                )
                draw_crystal_prompt(
                    painter,
                    view.width,
                    view.height,
                    frame.now,
                    self.attuning,
                    self.charge,
                )
            draw_status(painter, view.width, view.height, frame.now, self.level.bear)
            draw_compass(painter, view.width / 2, HUD_MARGIN, COMPASS_WIDTH, yaw)
            draw_banner(
                painter, view.width, view.height, self.level.number, self.level_time
            )
            if self.descent is not None:
                progress = self.descent / config.LEVEL_FADE_TIME
                darkness = 1.0 - abs(2.0 * progress - 1.0)
                painter.fillRect(
                    QRectF(0, 0, view.width, view.height),
                    with_alpha(BLACK, int(255 * darkness)),
                )
        elif self.death_time < DEATH_FLASH_TIME:
            flash = 1.0 - self.death_time / DEATH_FLASH_TIME
            painter.fillRect(
                QRectF(0, 0, view.width, view.height), with_alpha(RED, int(110 * flash))
            )

    def _threat(self) -> float:
        """0 unless the bear has your scent; then from faint, so the glow
        shows which way it is coming, to 1 when it is upon you."""
        bear = self.level.bear
        if not bear.hunting:
            return 0.0
        closeness = (
            config.NEAR_DISTANCE + 1 - bear.path_distance
        ) / config.NEAR_DISTANCE
        return 0.5 + 0.5 * clamp(closeness, 0.0, 1.0)
