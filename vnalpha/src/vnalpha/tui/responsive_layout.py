from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ResponsiveLayoutPolicy:
    compact_height: int = 24
    medium_height: int = 30
    compact_suggestion_limit: int = 4
    medium_suggestion_limit: int = 6
    full_suggestion_limit: int = 10
    footer_hidden_below_height: int = 20
    debug_drawer_min_height: int = 6
    debug_drawer_max_height: int = 14


class ResponsiveLayoutController:
    def __init__(self, policy: ResponsiveLayoutPolicy | None = None) -> None:
        self._policy: Final[ResponsiveLayoutPolicy] = (
            policy if policy is not None else ResponsiveLayoutPolicy()
        )

    @property
    def policy(self) -> ResponsiveLayoutPolicy:
        """Expose the immutable layout policy."""

        return self._policy

    def suggestion_limit(self, terminal_height: int) -> int:
        if terminal_height < self._policy.compact_height:
            return self._policy.compact_suggestion_limit
        if terminal_height < self._policy.medium_height:
            return self._policy.medium_suggestion_limit
        return self._policy.full_suggestion_limit

    def should_show_footer(self, terminal_height: int) -> bool:
        return terminal_height >= self._policy.footer_hidden_below_height

    def debug_drawer_height(self, terminal_height: int) -> int:
        proportional_height = terminal_height * 3 // 10
        return min(
            max(proportional_height, self._policy.debug_drawer_min_height),
            self._policy.debug_drawer_max_height,
        )
