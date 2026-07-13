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
    compact_height: int = 24
    medium_height: int = 30
    compact_suggestion_limit: int = 4
    medium_suggestion_limit: int = 6
    full_suggestion_limit: int = 10
    footer_hidden_below_height: int = 20


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

    def suggestion_limit(self, terminal_height: int) -> int:
        if terminal_height < self._policy.compact_height:
            return self._policy.compact_suggestion_limit
        if terminal_height < self._policy.medium_height:
            return self._policy.medium_suggestion_limit
        return self._policy.full_suggestion_limit

    def should_show_footer(self, terminal_height: int) -> bool:
        return terminal_height >= self._policy.footer_hidden_below_height
