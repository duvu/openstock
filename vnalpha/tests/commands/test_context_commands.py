from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection)
    yield connection
    connection.close()


def _workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workspaces"
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(root))
    return root


def test_context_status_returns_workspace_health(conn, tmp_path, monkeypatch) -> None:
    from vnalpha.commands.executor import CommandExecutor
    from vnalpha.workspace_context.lifecycle import (
        create_workspace,
        record_warning,
    )

    root = _workspace_root(tmp_path, monkeypatch)
    workspace = create_workspace(title="FPT workflow", mode="research", root=root)
    record_warning(workspace, "compact recommended", root=root)

    result = CommandExecutor(conn, surface="cli").execute("/context status")

    assert result.status == "SUCCESS"
    assert result.title == "/context status"
    assert result.summary is not None
    assert workspace.workspace_id in result.summary
    assert result.panels[0].title == "Workspace Health"
    assert result.panels[0].content["status"] == "active"
    assert result.panels[0].content["suggested_action"] == "/context compact"
