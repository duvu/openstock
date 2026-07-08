"""InputHistory — shell-like input history for the TUI composer."""

from __future__ import annotations


class InputHistory:
    """
    In-session input history with shell-like Up/Down navigation.

    Features:
    - push(text): appends non-empty, non-duplicate text
    - previous(current_draft): walks backward through history
    - next(): walks forward; restores draft past newest
    - reset_navigation(): exits navigation mode
    - Bounded by max_items (oldest evicted first)
    """

    def __init__(self, *, max_items: int = 500) -> None:
        self._items: list[str] = []
        self._max_items = max(1, max_items)
        self._index: int = -1  # -1 = not navigating
        self._draft: str = ""

    @property
    def navigating(self) -> bool:
        """True if currently navigating history."""
        return self._index >= 0

    def push(self, text: str) -> None:
        """Add input to history. Ignores empty/whitespace-only and consecutive dupes."""
        stripped = text.strip()
        if not stripped:
            return
        # Deduplicate consecutive
        if self._items and self._items[-1] == stripped:
            return
        self._items.append(stripped)
        # Enforce bounded size
        if len(self._items) > self._max_items:
            self._items = self._items[-self._max_items :]
        self.reset_navigation()

    def previous(self, current_draft: str) -> str | None:
        """
        Move backward through history.

        On first call, stores current_draft for later restoration.
        Returns the history item text, or None if history is empty.
        """
        if not self._items:
            return None
        if not self.navigating:
            # Entering navigation — save the current draft
            self._draft = current_draft
            self._index = len(self._items) - 1
        else:
            # Move further back
            if self._index > 0:
                self._index -= 1
            # else: clamp at oldest, return same item
        return self._items[self._index]

    def next(self) -> str | None:
        """
        Move forward through history.

        When moving past newest, restores the saved draft and exits navigation.
        Returns the item text, or None if not navigating.
        """
        if not self.navigating:
            return None
        self._index += 1
        if self._index >= len(self._items):
            # Past newest — restore draft
            draft = self._draft
            self.reset_navigation()
            return draft
        return self._items[self._index]

    def reset_navigation(self) -> None:
        """Exit history navigation mode."""
        self._index = -1
        self._draft = ""

    def items(self) -> list[str]:
        """Return a copy of all history items (oldest first)."""
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)
