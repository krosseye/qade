# SPDX-License-Identifier: GPL-3.0-or-later
"""The bear: sleeps, prowls, catches your scent, then hunts."""

import random
from enum import Enum, auto

from .config import LOSE_MARGIN, REAR_TIME
from .maze import Cell, Maze


class Mood(Enum):
    ASLEEP = auto()
    PROWLING = auto()
    REARING = auto()
    HUNTING = auto()


class Bear:
    def __init__(
        self,
        maze: Maze,
        cell: Cell,
        speed: float,
        wake_delay: float,
        scent_range: int,
        drift: float,
        prowl_pace: float,
        rng: random.Random,
    ):
        """A bear asleep in its lair at ``cell``.

        Args:
            maze: The level it hunts in.
            cell: Where it starts.
            speed: Cells per second while hunting.
            wake_delay: Seconds it lies in wait first.
            scent_range: Path distance, in cells, at which it smells you.
            drift: Chance, at each junction while prowling, of taking the
                way towards you rather than a random one.
            prowl_pace: Prowling speed, as a share of ``speed``.
            rng: Its choices while prowling.
        """
        self.maze = maze
        self.cell = cell
        self.next = cell
        self.came_from = cell
        self.progress = 0.0
        self.speed = speed
        self.scent_range = scent_range
        self.drift = drift
        self.prowl_pace = prowl_pace
        self.rng = rng
        self.mood = Mood.ASLEEP
        self.timer = wake_delay
        self.path_distance = 1 << 30
        self.called = False

    @property
    def awake(self) -> bool:
        return self.mood is not Mood.ASLEEP

    @property
    def hunting(self) -> bool:
        """Rearing or hunting: it has your scent."""
        return self.mood in (Mood.REARING, Mood.HUNTING)

    @property
    def position(self) -> tuple[float, float]:
        """Floor-plan position of its centre, between cells while moving."""
        (x0, z0), (x1, z1) = self.cell, self.next
        t = self.progress
        return (x0 + (x1 - x0) * t + 0.5, z0 + (z1 - z0) * t + 0.5)

    def step(self, dt: float, target: Cell, chiming: bool = False) -> None:
        """Advance one fixed step of stalking the player.

        Updates ``mood``, ``timer``, ``called``, ``path_distance`` and its
        movement (``cell``, ``next``, ``came_from``, ``progress``).

        Args:
            dt: Seconds in this step.
            target: The player's cell.
            chiming: The crystal at ``target`` is ringing this step.
        """
        to_target = self.maze.distances(target)
        self.path_distance = to_target[self.cell]
        self._sense(dt, heard=chiming)
        if self.mood in (Mood.ASLEEP, Mood.REARING):
            return

        pace = self.speed if self.mood is Mood.HUNTING else self.speed * self.prowl_pace
        if self.next == self.cell:
            self.next = self._choose(to_target)
        self.progress += pace * dt
        while self.progress >= 1.0:
            self.progress -= 1.0
            self.came_from, self.cell = self.cell, self.next
            self.next = self._choose(to_target)
            if self.next == self.cell:
                self.progress = 0.0
        self.path_distance = to_target[self.cell]

    def _sense(self, dt: float, heard: bool) -> None:
        """Change mood: wake, catch the scent or hear the chime, rear, charge,
        lose the trail."""
        if heard:
            self.called = True
        elif self.path_distance <= self.scent_range:
            self.called = False
        match self.mood:
            case Mood.ASLEEP if heard:
                self.mood, self.timer = Mood.REARING, REAR_TIME
            case Mood.ASLEEP:
                self.timer -= dt
                if self.timer <= 0:
                    self.mood = Mood.PROWLING
            case Mood.PROWLING if heard or self.path_distance <= self.scent_range:
                self.mood, self.timer = Mood.REARING, REAR_TIME
            case Mood.REARING:
                self.timer -= dt
                if self.timer <= 0:
                    self.mood = Mood.HUNTING
            case Mood.HUNTING if (
                not self.called and self.path_distance > self.scent_range + LOSE_MARGIN
            ):
                self.mood = Mood.PROWLING

    def _choose(self, to_target: dict[Cell, int]) -> Cell:
        """The next cell: towards the target when hunting, onward when prowling."""
        if to_target[self.cell] == 0:
            return self.cell
        options = [
            self.maze.step(self.cell, d) for d in self.maze.open_directions(self.cell)
        ]
        toward = min(options, key=to_target.__getitem__)
        if self.mood is Mood.HUNTING:
            return toward
        onward = [cell for cell in options if cell != self.came_from] or options
        if toward in onward and self.rng.random() < self.drift:
            return toward
        return self.rng.choice(onward)

    def approach(self, target: Cell) -> int | None:
        """The direction from ``target`` that leads, by the shortest path, to
        the bear: the way it will come at you. None if it is on ``target``."""
        to_bear = self.maze.distances(self.cell)
        if to_bear[target] == 0:
            return None
        return min(
            self.maze.open_directions(target),
            key=lambda d: to_bear[self.maze.step(target, d)],
        )
