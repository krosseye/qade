import random
from enum import StrEnum

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPen

from qade_engine import ArcadeGame, Frame, Phase
from qade_engine.core import clamp
from qade_engine.graphics import Opacity, current_theme, with_alpha
from qade_engine.input import InputMap, add_steering

from . import INFO

PLAYER_WIDTH, PLAYER_HEIGHT = 60.0, 14.0
PLAYER_SPEED = 480.0  # px/s
BLOCK_SIZE = 28.0
BLOCK_SPEED = 220.0  # px/s
SPAWN_INTERVAL = 0.45  # seconds between blocks


class Action(StrEnum):
    LEFT = "left"
    RIGHT = "right"


LEFT_KEYS = (Qt.Key.Key_Left, Qt.Key.Key_A)
RIGHT_KEYS = (Qt.Key.Key_Right, Qt.Key.Key_D)


class Dodge(ArcadeGame):
    INFO = INFO
    CANVAS_SIZE = (800, 600)
    # Steering keys shouldn't skip the game-over screen.
    NEVER_CONFIRM = (*LEFT_KEYS, *RIGHT_KEYS)
    INTRO_LINES = ("BLOCKS WILL FALL.", "DO NOT GET HIT.")
    GAME_OVER_TITLE = "FLATTENED"

    def build_input_map(self) -> InputMap:
        controls = InputMap()
        # The keys, plus both sticks, the d-pad, bumpers and triggers.
        add_steering(controls, Action.LEFT, Action.RIGHT, LEFT_KEYS, RIGHT_KEYS)
        return controls

    def reset(self) -> None:
        self.player_x = self.field.width / 2
        self.blocks: list[QRectF] = []
        self.spawn_timer = 0.0

    def step_playing(self, dt: float) -> None:
        direction = self.actions.is_pressed(Action.RIGHT) - self.actions.is_pressed(
            Action.LEFT
        )
        half = PLAYER_WIDTH / 2
        self.player_x = clamp(
            self.player_x + direction * PLAYER_SPEED * dt, half, self.field.width - half
        )

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer += SPAWN_INTERVAL
            x = random.uniform(0, self.field.width - BLOCK_SIZE)
            self.blocks.append(QRectF(x, -BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))

        for block in self.blocks:
            block.translate(0, BLOCK_SPEED * dt)
        survivors = [b for b in self.blocks if b.top() < self.field.height]
        self.score += len(self.blocks) - len(survivors)  # one point per block dodged
        self.blocks = survivors

        if any(block.intersects(self.player_rect()) for block in self.blocks):
            self.died()

    def player_rect(self) -> QRectF:
        top = self.field.height - 60
        return QRectF(
            self.player_x - PLAYER_WIDTH / 2, top, PLAYER_WIDTH, PLAYER_HEIGHT
        )

    def draw_world(self, frame: Frame) -> None:
        theme = current_theme()
        painter = frame.painter

        painter.setPen(QPen(theme.danger, 2))
        painter.setBrush(with_alpha(theme.danger, Opacity.FAINT))
        for block in self.blocks:
            painter.drawRect(block)

        if self.phase is not Phase.GAME_OVER:  # the paddle is gone once hit
            painter.setPen(QPen(theme.accent, 2))
            painter.setBrush(with_alpha(theme.accent, Opacity.MEDIUM))
            painter.drawRect(self.player_rect())
