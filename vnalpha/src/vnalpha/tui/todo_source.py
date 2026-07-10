from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from vnalpha.workspace_context.models import WorkspaceState, WorkspaceTask

from vnalpha.workspace_context.lifecycle import get_or_create_latest_workspace


@dataclass(frozen=True, slots=True)
class TodoItem:
    """Read-only task item rendered in the TUI TODO panel."""

    id: str
    title: str
    status: str = "open"
    priority: str = "p2"
    source: str = "fallback"
    symbol: str | None = None
    detail: str | None = None


class TodoSource(Protocol):
    """Source contract for read-only TODO panel items."""

    def load_items(self) -> list[TodoItem]:
        """Load current TODO items."""


@dataclass(frozen=True, slots=True)
class FallbackTodoSource:
    """Provide safe read-only hints when workspace tasks are unavailable."""

    def load_items(self) -> list[TodoItem]:
        return []


@dataclass(frozen=True, slots=True)
class WorkspaceTodoSource:
    """Adapt workspace-context state into TODO items for the TUI."""

    loader: "Callable[[], WorkspaceState] | None" = None

    def load_items(self) -> list[TodoItem]:
        """Load read-only TODO items from workspace context when available."""

        load_workspace = (
            self.loader if self.loader is not None else get_or_create_latest_workspace
        )
        try:
            state = load_workspace()
        except FileNotFoundError:
            return []
        return [
            *self._task_items(state.open_tasks),
            *self._warning_items(state.warnings),
        ]

    def _task_items(self, tasks: list["WorkspaceTask"]) -> list[TodoItem]:
        return [self._map_task(task) for task in tasks]

    def _warning_items(self, warnings: list[str]) -> list[TodoItem]:
        return [
            TodoItem(
                id=f"warning:{index}",
                title=warning,
                status="blocked",
                priority="p1",
                source="system",
            )
            for index, warning in enumerate(warnings, start=1)
        ]

    def _map_task(self, task: "WorkspaceTask") -> TodoItem:
        return TodoItem(
            id=task.task_id,
            title=task.text,
            status=_map_workspace_status(task.status),
            priority=_map_workspace_priority(task.priority),
            source="workspace",
        )


@dataclass(frozen=True, slots=True)
class CompositeTodoSource:
    """Merge multiple TODO sources while removing duplicates."""

    sources: list[TodoSource]

    def load_items(self) -> list[TodoItem]:
        ordered_items: list[TodoItem] = []
        seen_keys: set[str] = set()
        for source in self.sources:
            for item in source.load_items():
                dedupe_key = item.id or f"{item.source}:{item.title}"
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                ordered_items.append(item)
        return ordered_items


_STATUS_PRIORITY: Final[dict[str, str]] = {
    "pending": "open",
    "open": "open",
    "in_progress": "active",
    "active": "active",
    "blocked": "blocked",
    "completed": "done",
    "done": "done",
}

_PRIORITY_PRIORITY: Final[dict[str, str]] = {
    "high": "p1",
    "medium": "p2",
    "low": "p3",
    "p0": "p0",
    "p1": "p1",
    "p2": "p2",
    "p3": "p3",
}


def _map_workspace_status(status: str) -> str:
    """Map workspace task statuses onto read-only TODO panel statuses."""

    return _STATUS_PRIORITY.get(status, "open")


def _map_workspace_priority(priority: str) -> str:
    """Map workspace task priority labels onto compact TODO priority badges."""

    return _PRIORITY_PRIORITY.get(priority, "p2")
