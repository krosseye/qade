# SPDX-License-Identifier: GPL-3.0-or-later
"""A small, table-driven state machine with timed transitions."""

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import Generic, TypeVar

S = TypeVar("S", bound=Enum)
E = TypeVar("E", bound=Enum)


class TransitionStyle(Enum):
    """How a timed transition looks. The renderer decides what each means.

    Attributes:
        FADE: Fade to black, switch state, fade back in.
    """

    FADE = auto()


@dataclass(frozen=True)
class Edge(Generic[S]):
    """Where an event leads from a given state.

    Attributes:
        target: The state to change to.
        times: Fire on the Nth time the event arrives in this state.
        style: How the change looks. None switches instantly.
        duration: Seconds a styled change takes. 0 switches instantly.
    """

    target: S
    times: int = 1
    style: TransitionStyle | None = None
    duration: float = 0.0


@dataclass
class Transition(Generic[S]):
    """A timed change in progress. The state switches halfway through.

    Attributes:
        source: The state being left.
        target: The state being entered.
        style: How the change looks.
        duration: Total seconds.
        elapsed: Seconds played so far.
    """

    source: S
    target: S
    style: TransitionStyle
    duration: float
    elapsed: float = 0.0

    @property
    def progress(self) -> float:
        """How far through the change, from 0 at the start to 1 at the end."""
        return min(self.elapsed / self.duration, 1.0)

    @property
    def switched(self) -> bool:
        """Whether the state has switched to the target yet."""
        return self.progress >= 0.5


class StateMachine(Generic[S, E]):
    """Tracks the current state, the time spent in it, and any transition.

    The legal moves are a table of ``(state, event) -> Edge``. Time only moves
    through ``advance``, so the machine runs on whatever clock steps it.

    Attributes:
        state: The current state.
        time_in_state: Seconds since the state was entered, not counting
            transitions.
        transition: The timed change playing, if any.
    """

    def __init__(
        self,
        initial: S,
        edges: Mapping[tuple[S, E], Edge[S]],
        timeout_event: E,
        timeouts: Mapping[S, float] | None = None,
        on_change: Callable[[S, S], None] | None = None,
    ) -> None:
        """Creates the machine in its initial state.

        Args:
            initial: The starting state.
            edges: Every legal move, keyed by (state, event).
            timeout_event: The event sent when a state times out.
            timeouts: Seconds after which each listed state times out.
            on_change: Called with (source, target) each time the state changes.
        """
        self.state = initial
        self.time_in_state = 0.0
        self.transition: Transition[S] | None = None
        self._edges = edges
        self._timeout_event = timeout_event
        self._timeouts = timeouts or {}
        self._on_change = on_change
        self._counts: Counter[E] = Counter()
        self._timed_out = False

    def send(self, event: E) -> bool:
        """Applies an event.

        Events are ignored while a transition plays, except those with an
        instant edge, which cut it short, so nothing can lose a player's death.

        Args:
            event: What happened.

        Returns:
            True if it started a change of state.
        """
        edge = self._edges.get((self.state, event))
        if edge is None:
            return False
        style = edge.style if edge.duration > 0 else None
        if self.transition is not None and style is not None:
            return False
        self._counts[event] += 1
        if self._counts[event] < edge.times:
            return False

        if style is None:
            self.transition = None
            self._change(edge.target)
        else:
            self.transition = Transition(self.state, edge.target, style, edge.duration)
        return True

    def advance(self, dt: float) -> None:
        """Moves time forward: plays any transition, else checks for a timeout.

        Args:
            dt: Seconds to advance. Must be finite and non-negative: a NaN
                leaves a transition stuck halfway forever.
        """
        if self.transition is not None:
            transition = self.transition
            was_switched = transition.switched
            transition.elapsed += dt
            if transition.switched and not was_switched:
                self._change(transition.target)
            if transition.progress >= 1.0:
                self.transition = None
            return

        self.time_in_state += dt
        limit = self._timeouts.get(self.state)
        if limit is not None and not self._timed_out and self.time_in_state >= limit:
            self._timed_out = True
            self.send(self._timeout_event)

    def _change(self, target: S) -> None:
        source = self.state
        self.state = target
        self.time_in_state = 0.0
        self._counts.clear()
        self._timed_out = False
        if self._on_change is not None:
            self._on_change(source, target)
