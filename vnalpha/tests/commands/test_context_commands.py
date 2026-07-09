from __future__ import annotations

import json
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


def test_context_compact_writes_compact_file(conn, tmp_path, monkeypatch) -> None:
    from vnalpha.commands.executor import CommandExecutor
    from vnalpha.workspace_context.lifecycle import (
        create_workspace,
        record_artifact,
        record_warning,
    )
    from vnalpha.workspace_context.models import WorkspaceArtifactRef

    root = _workspace_root(tmp_path, monkeypatch)
    workspace = create_workspace(title="HPG workflow", mode="research", root=root)
    record_artifact(
        workspace,
        WorkspaceArtifactRef(
            artifact_id="artifact-1",
            artifact_type="report",
            path="artifacts/report.md",
            summary="Breakout evidence snapshot",
            created_at="2026-07-09T01:10:00+00:00",
            source_refs=["artifact:evidence-1"],
        ),
        root=root,
    )
    record_warning(workspace, "stale compact", root=root)

    result = CommandExecutor(conn, surface="cli").execute("/context compact")

    compact_path = root / workspace.workspace_id / "compact.md"
    events_path = root / workspace.workspace_id / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert result.status == "SUCCESS"
    assert result.title == "/context compact"
    assert compact_path.exists()
    assert "compact.md" in (result.summary or "")
    assert result.panels[0].title == "Compaction"
    assert result.panels[0].content["compact_path"] == "compact.md"
    assert any(event["event_type"] == "WORKSPACE_COMPACTED" for event in events)


def test_context_clean_dry_run_returns_clean_plan(conn, tmp_path, monkeypatch) -> None:
    from vnalpha.commands.executor import CommandExecutor
    from vnalpha.workspace_context.lifecycle import create_workspace

    root = _workspace_root(tmp_path, monkeypatch)
    workspace = create_workspace(title="VCI workflow", mode="research", root=root)
    stale_path = root / workspace.workspace_id / "artifacts" / "stale.tmp"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("old", encoding="utf-8")

    result = CommandExecutor(conn, surface="cli").execute("/context clean --dry-run")

    assert result.status == "SUCCESS"
    assert result.title == "/context clean"
    assert result.summary is not None
    assert "dry run" in result.summary.lower()
    assert result.panels[0].title == "Clean Plan"
    assert "artifacts/stale.tmp" in result.panels[0].content["remove"]
    assert stale_path.exists()


def test_context_clean_execution_archives_and_removes_files(conn, tmp_path, monkeypatch) -> None:
    from vnalpha.commands.executor import CommandExecutor
    from vnalpha.workspace_context.lifecycle import create_workspace

    root = _workspace_root(tmp_path, monkeypatch)
    workspace = create_workspace(title="SSI workflow", mode="research", root=root)
    workspace_dir = root / workspace.workspace_id
    stale_path = workspace_dir / "artifacts" / "stale.tmp"
    old_events_path = workspace_dir / "events.old.jsonl"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("old", encoding="utf-8")
    old_events_path.write_text("old events", encoding="utf-8")

    result = CommandExecutor(conn, surface="cli").execute("/context clean")

    assert result.status == "SUCCESS"
    assert result.title == "/context clean"
    assert result.panels[0].title == "Clean Result"
    assert "archive/events.old.jsonl" in result.panels[0].content["archived"]
    assert "artifacts/stale.tmp" in result.panels[0].content["removed"]
    assert not stale_path.exists()
    assert not old_events_path.exists()
    assert (root / "archive" / workspace.workspace_id / "events.old.jsonl").exists()


def test_context_requires_supported_subcommand(conn) -> None:
    from vnalpha.commands.executor import CommandExecutor

    result = CommandExecutor(conn, surface="cli").execute("/context resume")

    assert result.status == "VALIDATION_ERROR"
    assert result.error is not None
    assert result.error.error_type == "CommandValidationError"
    assert "Unsupported /context subcommand" in result.error.message
