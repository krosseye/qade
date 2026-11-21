# SPDX-License-Identifier: GPL-3.0-or-later
"""Boarded Up: hold the house against the horde, round after round."""

from PySide6.QtCore import QPointF, QRectF

from qade_engine import ArcadeGame, Frame, Phase
from qade_engine.audio import SoundBus
from qade_engine.core import clamp, lerp
from qade_engine.graphics import RED, ParticleEffect, Shape, current_theme
from qade_engine.input import InputMap
from qade_engine.ui import HUD_MARGIN, HudRow, hud_panel_height

from . import INFO, controls, music, sounds
from .controls import Action
from .layout import build_house
from .render import (
    ICHOR,
    ROT,
    TILE,
    WOOD,
    HouseArt,
    Popup,
    Tracer,
    draw_banner,
    draw_doors,
    draw_hurt,
    draw_offscreen,
    draw_player,
    draw_popups,
    draw_prompt,
    draw_tracers,
    draw_windows,
    draw_zombie,
    to_px,
)
from .sim import REGEN_TIME, Sim

CAMERA_MARGIN = 72
CAMERA_BELOW = 90

_GORE = (
    ParticleEffect(
        count=14,
        life=(0.25, 0.6),
        colors=(ROT, ICHOR.darker(300)),
        shapes=(Shape.SHARD, Shape.DOT),
        speed=(40, 160),
        size=(2, 6),
        drag=3.0,
        spin=(90, 360),
        width=1.6,
    ),
    ParticleEffect(
        count=6,
        life=(0.2, 0.45),
        colors=(RED, RED.darker(300)),
        speed=(30, 90),
        size=(2, 3),
        drag=3.0,
    ),
    ParticleEffect(
        count=1, life=(0.3, 0.3), colors=(ROT, ROT), shapes=(Shape.RING,), size=(16, 16)
    ),
)
_SPLINTERS = (
    ParticleEffect(
        count=7,
        life=(0.3, 0.6),
        colors=(WOOD, WOOD.darker(250)),
        shapes=(Shape.SHARD,),
        speed=(30, 120),
        size=(4, 8),
        drag=3.0,
        spin=(180, 540),
        width=1.5,
    ),
)


class BoardedUp(ArcadeGame):
    INFO = INFO
    CANVAS_SIZE = (800, 600)
    TRANSMISSION_TITLE = "EMERGENCY BROADCAST // ON REPEAT"
    STANDBY_MESSAGE = "THE RADIO HASN'T CHANGED IN DAYS"
    STANDBY_PROMPT = "[ PRESS ANY KEY TO HOLD OUT ]"
    INTRO_LINES = (
        "THIS IS NOT A TEST. STAY INDOORS.",
        "BOARD UP YOUR WINDOWS. THEY COME AT NIGHT.",
        "IF THEY GET IN, DO NOT LET THEM CORNER YOU.",
        "RESCUE CONVOYS ARE ON THEIR WAY.",
        "HOLD OUT. HELP IS ONLY HOURS AWAY.",
        "THIS MESSAGE WILL REPEAT.",
    )
    INTRO_HIGHLIGHTS = ("DO NOT LET THEM CORNER YOU", "WILL REPEAT")
    INTRO_PROMPT = STANDBY_PROMPT
    GAME_OVER_TITLE = "OVERRUN // THE CONVOY NEVER CAME"
    GAME_OVER_PROMPT = "[ PRESS ANY KEY TO WAIT AGAIN ]"
    HUD_TITLE = "SURVIVOR"
    NEVER_CONFIRM = controls.MOVEMENT_KEYS
    STARS_IN_PLAY = False
    MUSIC = music.round_song(1)
    GAME_OVER_DELAY = music.GAME_OVER_SECOND_BAR

    def register_sounds(self, bus: SoundBus) -> None:
        sounds.register(bus)

    def build_input_map(self) -> InputMap:
        return controls.input_map()

    def reset(self) -> None:
        self.sim = Sim(build_house(self.rng), self.rng)
        self.art = HouseArt(self.sim.house)
        self.tracers: list[Tracer] = []
        self.popups: list[Popup] = []
        self.round_time = 99.0
        self.hurt_glow = 0.0

    def step_playing(self, dt: float) -> None:
        a = self.actions
        move = (
            a.is_pressed(Action.RIGHT) - a.is_pressed(Action.LEFT),
            a.is_pressed(Action.DOWN) - a.is_pressed(Action.UP),
        )
        fx = self.sim.step(dt, move, a.is_pressed(Action.ACT))
        self.score = self.sim.earned
        self._age(dt)
        for start, end in fx.shots:
            self.tracers.append(Tracer(to_px(*start), to_px(*end)))
            self.play_sound(sounds.SHOT)
        for x, y in fx.kills:
            self.particles.emit(_GORE, x * TILE, y * TILE)
            self.play_sound(sounds.KILL)
        for at, amount in fx.points:
            self.popups.append(Popup(to_px(*at), f"+{amount}"))
        for window in fx.torn:
            x, y = window.center
            self.particles.emit(_SPLINTERS, x * TILE, y * TILE)
            self.play_sound(sounds.TEAR)
        if fx.boarded:
            self.play_sound(sounds.BOARD)
        if fx.opened:
            self.play_sound(sounds.DOOR)
        if fx.hurt:
            self.hurt_glow = 1.0
            self.play_sound(sounds.HURT)
        if fx.round_started:
            self.round_time = 0.0
            self.play_sound(sounds.ROUND)
            self.play_music(music.round_song(fx.round_started))
        if fx.round_cleared:
            self.play_music(music.BETWEEN_ROUNDS)
        if self.sim.downed:
            self.died()
            self.play_music(music.GAME_OVER)
            self.play_music(None)

    def step_aftermath(self, dt: float) -> None:
        self._age(dt)

    def _age(self, dt: float) -> None:
        self.particles.update(dt)
        self.round_time += dt
        for t in self.tracers:
            t.life -= dt
        self.tracers = [t for t in self.tracers if t.life > 0]
        for p in self.popups:
            p.life -= dt * 1.2
        self.popups = [p for p in self.popups if p.life > 0]
        if self.sim.hits:
            self.hurt_glow = max(0.35, self.sim.regen / REGEN_TIME)
        else:
            self.hurt_glow = max(0.0, self.hurt_glow - dt * 2)

    def hud_rows(self) -> list[HudRow]:
        theme = current_theme()
        rows = super().hud_rows()
        rows.insert(2, HudRow("ROUND", f"{self.sim.round:02d}", theme.text))
        rows.insert(3, HudRow("POINTS", f"{self.sim.points:5d}", theme.highlight))
        return rows

    def _camera(self, width: float, height: float, player: QPointF) -> QPointF:
        house = self.sim.house
        top = HUD_MARGIN + hud_panel_height(len(self.hud_rows())) + 10
        x = clamp(
            player.x() - width / 2,
            -CAMERA_MARGIN,
            max(-CAMERA_MARGIN, house.width * TILE - width + CAMERA_MARGIN),
        )
        y = clamp(
            player.y() - height / 2,
            -top,
            max(-top, house.height * TILE - height + CAMERA_BELOW),
        )
        return QPointF(x, y)

    def draw_world(self, frame: Frame) -> None:
        painter, view, now, alpha = frame.painter, frame.view, frame.now, frame.alpha
        sim = self.sim
        player = to_px(lerp(sim.prev[0], sim.x, alpha), lerp(sim.prev[1], sim.y, alpha))
        zombies = [
            (z, to_px(lerp(z.prev[0], z.x, alpha), lerp(z.prev[1], z.y, alpha)))
            for z in sim.zombies
        ]
        camera = self._camera(view.width, view.height, player)

        painter.save()
        painter.translate(-camera)
        self.art.draw(painter, lantern=player)
        draw_windows(painter, sim.house, sim.tearing(), now)
        draw_doors(painter, sim.house, sim.points, now)
        for z, at in zombies:
            draw_zombie(painter, at, z)
        draw_player(painter, player, sim, now)
        draw_tracers(painter, self.tracers)
        self.particles.draw(painter, alpha * self.dt)
        draw_popups(painter, self.popups)
        painter.restore()

        draw_offscreen(
            painter,
            QRectF(0, 0, view.width, view.height),
            [at - camera for _, at in zombies],
        )
        draw_hurt(painter, view.width, view.height, self.hurt_glow)
        if self.phase is not Phase.GAME_OVER:
            draw_banner(painter, view.width, view.height, sim, self.round_time)
            draw_prompt(painter, view.width, view.height, sim, now)
