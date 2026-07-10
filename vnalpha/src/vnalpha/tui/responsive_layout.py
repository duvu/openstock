from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ResponsiveLayoutPolicy:
    """Responsive width policy for the optional TODO side rail."""

    todo_visible_min_width: int = 120
    todo_min_width: int = 28
    todo_preferred_width: int = 32
    todo_max_width: int = 40


class ResponsiveLayoutController:
    """Compute TODO visibility and width from terminal size and user preference."""

    def __init__(self, policy: ResponsiveLayoutPolicy | None = None) -> None:
        self._policy: Final[ResponsiveLayoutPolicy] = (
            policy if policy is not None else ResponsiveLayoutPolicy()
        )

    @property
    def policy(self) -> ResponsiveLayoutPolicy:
        """Expose the immutable layout policy."""

        return self._policy

    def should_show_todo(
        self, terminal_width: int, user_preference: bool | None
    ) -> bool:
        """Return whether the TODO panel should be visible."""

        if terminal_width < self._policy.todo_visible_min_width:
            return False
        if user_preference is False:
            return False
        return True

    def todo_width(self, terminal_width: int) -> int:
        """Return a bounded width for the TODO rail."""

        available_width = terminal_width // 4
        preferred_width = max(available_width, self._policy.todo_min_width)
        return min(preferred_width, self._policy.todo_max_width)
