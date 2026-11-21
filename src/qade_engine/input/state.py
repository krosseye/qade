# SPDX-License-Identifier: GPL-3.0-or-later
"""Which actions are held, and which were just pressed."""

from collections.abc import Iterable, Mapping


class ActionState:
    """The current strength of every action, for game steps to read."""

    def __init__(self) -> None:
        """Creates a state with nothing held."""
        self._strengths: dict[str, float] = {}
        self._presses: set[str] = set()
        self._known: frozenset[str] | None = None

    def expect(self, actions: Iterable[str]) -> None:
        """Names every action, so reading any other raises ``KeyError``.

        The host calls this when it switches apps. Until then any name reads
        as not held, so headless tests can apply just the actions they need.

        Args:
            actions: The running app's action names.
        """
        self._known = frozenset(actions)

    def _check(self, action: str) -> None:
        if self._known is not None and action not in self._known:
            raise KeyError(f"no action named {action!r} in the input map")

    def is_pressed(self, action: str) -> bool:
        """Whether an action is held.

        Args:
            action: The action's name.

        Returns:
            True while it is held.

        Raises:
            KeyError: The input map has no such action.
        """
        self._check(action)
        return self._strengths.get(action, 0.0) > 0.0

    def was_pressed(self, action: str) -> bool:
        """Whether an action was pressed since the last step.

        A tap too quick for ``is_pressed`` to see still counts, in exactly one
        step.

        Args:
            action: The action's name.

        Returns:
            True if it was pressed, even if released again since.

        Raises:
            KeyError: The input map has no such action.
        """
        self._check(action)
        return action in self._presses

    def strength(self, action: str) -> float:
        """How strongly an action is held.

        Args:
            action: The action's name.

        Returns:
            Its strength, from 0 to 1.

        Raises:
            KeyError: The input map has no such action.
        """
        self._check(action)
        return self._strengths.get(action, 0.0)

    def apply(self, strengths: Mapping[str, float]) -> list[str]:
        """Replaces every strength and records what was just pressed.

        Args:
            strengths: New strength per action.

        Returns:
            The actions that were just pressed.
        """
        was_pressed = {a for a, s in self._strengths.items() if s > 0.0}
        self._strengths = dict(strengths)
        pressed = [a for a, s in strengths.items() if s > 0.0 and a not in was_pressed]
        self._presses.update(pressed)
        return pressed

    def clear_presses(self) -> None:
        """Forgets the presses ``was_pressed`` reports.

        The host calls this after every step.
        """
        self._presses.clear()
