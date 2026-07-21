from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

textual_available = True
try:
    import textual  # noqa: F401
except ImportError:
    textual_available = False

skip_if_no_textual = pytest.mark.skipif(
    not textual_available, reason="textual not installed"
)


def _empty_conn():
    import duckdb

    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    return conn


@pytest.fixture
def mock_get_connection():
    with patch(
        "vnalpha.warehouse.connection.get_connection", return_value=_empty_conn()
    ):
        yield


def _workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workspaces"
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(root))
    return root


def _renderable_text(renderable: object) -> str:
    from rich.console import Console

    console = Console(record=True, width=120)
    console.print(renderable)
    return console.export_text()


def test_workspace_todo_source_maps_workspace_state_to_items() -> None:
    from vnalpha.tui.todo_source import WorkspaceTodoSource
    from vnalpha.workspace_context.models import WorkspaceState, WorkspaceTask

    state = WorkspaceState(
        workspace_id="ws-1",
        title="FPT workspace",
        status="active",
        mode="research",
        created_at="2026-07-10T00:00:00+00:00",
        updated_at="2026-07-10T00:05:00+00:00",
        open_tasks=[
            WorkspaceTask(
                task_id="task-1",
                text="Review FPT breakout",
                status="in_progress",
                priority="high",
                created_at="2026-07-10T00:00:00+00:00",
                updated_at="2026-07-10T00:01:00+00:00",
            )
        ],
        warnings=["Data freshness warning"],
    )
    source = WorkspaceTodoSource(loader=lambda: state)

    items = source.load_items()

    assert [item.id for item in items] == ["task-1", "warning:1"]
    assert items[0].status == "active"
    assert items[0].priority == "p1"
    assert items[1].status == "blocked"
    assert items[1].source == "system"
