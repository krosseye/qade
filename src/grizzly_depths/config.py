# SPDX-License-Identifier: GPL-3.0-or-later
"""Grizzly Depths tuning. Distances are in cells; times in seconds."""

from qade_engine.core import clamp

CANVAS_WIDTH, CANVAS_HEIGHT = 800, 600

# player
STEP_TIME = 0.2  # between steps while a move key is held
TURN_TIME = 0.16  # after a quarter turn
BUMP_TIME = 0.12  # after walking into a wall
CAMERA_FREQUENCY = 16.0  # camera spring (rad/s)
EYE_HEIGHT = 0.5  # walls are 1 tall

# levels
LOOP_FRACTION = 0.08  # share of leftover walls knocked out to make loops
LEVEL_FADE_TIME = 1.2  # fade out, build the next level, fade in
EXIT_SCORE = 100  # times the level number, for reaching an exit
ATTUNE_FADE_TIME = 2.0  # for a released charge to drain
RAMP_LEVELS = 14  # levels after the first until difficulty stops rising


# bear
REAR_TIME = 0.8  # seconds it rears and roars before charging
LOSE_MARGIN = 2  # cells past scent range before it loses the trail
CATCH_DISTANCE = 0.55  # centre to centre, on the floor plan
NEAR_DISTANCE = 4  # "RUN", and the edge glow brightens from here
APPROACH_DISTANCE = 9  # the heartbeat starts here, also scales footsteps

# view
VIEW_RADIUS = 7.5  # nothing further is drawn
DEATH_TURN_FREQUENCY = 9.0  # how fast you turn to face the bear when caught


def _ease(level: int, first: float, limit: float, levels: int) -> float:
    """``first`` on level 1, reaching ``limit`` after ``levels`` more."""
    t = clamp((level - 1) / levels, 0.0, 1.0)
    return first + (limit - first) * t


MAX_MAZE_SIZE = 16


def maze_size(level: int) -> int:
    return min(6 + level, MAX_MAZE_SIZE)


GROWTH_LEVELS = MAX_MAZE_SIZE - maze_size(1)


def attune_time(level: int) -> float:
    """Holding attune on the exit crystal, to charge it and escape. Grows with
    the maze, so the chime-called bear still arrives close to the finish."""
    return _ease(level, 3.5, 6.0, GROWTH_LEVELS)


def braid(level: int) -> float:
    """Share of dead ends opened up: fewer traps early on."""
    return _ease(level, 0.9, 0.4, RAMP_LEVELS)


def bear_speed(level: int) -> float:
    """Cells per second when hunting; the player manages about 4 with turns."""
    return _ease(level, 1.2, 2.8, RAMP_LEVELS)


def wake_delay(level: int) -> float:
    return _ease(level, 12.0, 4.0, RAMP_LEVELS)


def scent_range(level: int) -> int:
    """Path distance at which the bear smells you and charges. Grows with the
    maze, so a bigger maze doesn't make it slower to find you."""
    return round(_ease(level, 4, 8, GROWTH_LEVELS))


def drift(level: int) -> float:
    """How often the prowling bear heads your way at a junction. Ramps with
    the maze's growth, so a bigger maze doesn't make it harder to find you."""
    return _ease(level, 0.3, 0.9, GROWTH_LEVELS)


def prowl_pace(level: int) -> float:
    """Prowling speed, as a share of hunting speed. Ramps with the maze's
    growth, so the bear still covers a bigger maze in time to find you."""
    return _ease(level, 0.6, 0.8, GROWTH_LEVELS)
