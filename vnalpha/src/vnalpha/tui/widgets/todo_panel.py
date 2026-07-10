from __future__ import annotations

from rich.console import Group
from rich.text import Text

from vnalpha.tui.todo_source import FallbackTodoSource, TodoItem, TodoSource

try:
    from textual.reactive import reactive
    from textual.widget import Widget

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


def _group_items(items: list[TodoItem]) -> dict[str, list[TodoItem]]:
    active_items = [item for item in items if item.status == "active"]
    blocked_items = [item for item in items if item.status == "blocked"]
    done_items = [item for item in items if item.status == "done"]
    next_items = [
        item for item in items if item.status not in {"active", "blocked", "done"}
    ]
    return {
        "ACTIVE": active_items,
        "BLOCKED": blocked_items,
        "NEXT": next_items,
        "RECENTLY DONE": done_items,
    }


def _item_line(item: TodoItem) -> Text:
    return Text.assemble(
        (f"{item.priority.upper()} ", "bold cyan"),
        (item.title, "white"),
    )


def _render_items(items: list[TodoItem]) -> Group:
    if not items:
        return Group(
            Text("TODOs", style="bold"),
            Text("No TODOs yet", style="dim"),
            Text('Use /todo add "..." to add a task.', style="dim"),
        )

    parts: list[Text] = [Text("TODOs", style="bold")]
    for title, grouped_items in _group_items(items).items():
        if not grouped_items:
            continue
        parts.append(Text(title, style="bold yellow" if title == "BLOCKED" else "bold"))
        parts.extend(_item_line(item) for item in grouped_items)
    return Group(*parts)


if _TEXTUAL_AVAILABLE:

    class TodoPanel(Widget):
        """Read-only responsive TODO side rail for the chat-first TUI."""

        DEFAULT_CSS = """
        TodoPanel {
            width: 32;
            min-width: 28;
            max-width: 40;
            border: round $accent;
            padding: 0 1;
            display: block;
        }
        """

        renderable = reactive(Group(Text("TODOs")), layout=False)

        def __init__(
            self,
            source: TodoSource | None = None,
            items: list[TodoItem] | None = None,
            **kwargs,
        ) -> None:
            super().__init__(**kwargs)
            self._source = source if source is not None else FallbackTodoSource()
            self._items = list(items) if items is not None else None
            self.can_focus = False
            self.refresh_items()

        def render(self) -> Group:
            return self.renderable

        def refresh_items(self) -> None:
            """Reload items from the source and refresh the renderable."""

            loaded_items = (
                self._items if self._items is not None else self._source.load_items()
            )
            self.renderable = _render_items(loaded_items)
            self._emit_refreshed(loaded_items)

        def set_items(self, items: list[TodoItem]) -> None:
            """Replace the current items with explicit read-only content."""

            self._items = list(items)
            self.refresh_items()

        def _emit_refreshed(self, items: list[TodoItem]) -> None:
            try:
                from vnalpha.observability.audit import log_audit

                log_audit(
                    "TUI_TODO_PANEL_REFRESHED",
                    f"count={len(items)}",
                    module="vnalpha.tui.widgets.todo_panel",
                )
            except Exception:
                pass

else:

    class TodoPanel:  # type: ignore[no-redef]
        """Importable fallback used when textual is unavailable."""

        renderable = Group(Text("TODOs"))

        def __init__(
            self,
            source: TodoSource | None = None,
            items: list[TodoItem] | None = None,
            **kwargs,
        ) -> None:
            self._source = source if source is not None else FallbackTodoSource()
            self._items = list(items) if items is not None else None
            self.display = True
            self.can_focus = False
            self.refresh_items()

        def refresh_items(self) -> None:
            loaded_items = (
                self._items if self._items is not None else self._source.load_items()
            )
            self.renderable = _render_items(loaded_items)

        def set_items(self, items: list[TodoItem]) -> None:
            self._items = list(items)
            self.refresh_items()
