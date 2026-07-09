from __future__ import annotations

import json

from vnalpha.workspace_context.lifecycle import (
    archive_workspace,
    create_workspace,
    get_or_create_latest_workspace,
    get_status,
    list_workspaces,
    record_artifact,
    record_error,
    record_input,
    record_warning,
    resume_workspace,
)
from vnalpha.workspace_context.models import WorkspaceArtifactRef


def test_create_resume_and_status_flow(tmp_path) -> None:
    workspace = create_workspace(title="FPT workflow", mode="research", root=tmp_path)

    assert workspace.workspace_id.startswith("ws-")
    assert workspace.title == "FPT workflow"
    assert workspace.status == "active"

    resumed = resume_workspace(workspace.workspace_id, root=tmp_path)
    report = get_status(workspace.workspace_id, root=tmp_path)

    assert resumed.workspace_id == workspace.workspace_id
    assert report.workspace_id == workspace.workspace_id
    assert report.title == "FPT workflow"
    assert report.mode == "research"
    assert report.status == "active"


def test_get_or_create_latest_and_list_workspaces(tmp_path) -> None:
    first = get_or_create_latest_workspace(root=tmp_path)
    again = get_or_create_latest_workspace(root=tmp_path)
    all_workspaces = list_workspaces(root=tmp_path)

    assert again.workspace_id == first.workspace_id
    assert [item.workspace_id for item in all_workspaces] == [first.workspace_id]


def test_record_input_artifact_warning_error_and_archive(tmp_path) -> None:
    workspace = create_workspace(title="FPT workflow", mode="research", root=tmp_path)

    record_input(
        workspace,
        "api_key=secret compare FPT and HPG",
        "user",
        source="tui",
        root=tmp_path,
    )
    record_artifact(
        workspace,
        WorkspaceArtifactRef(
            artifact_id="watchlist-1",
            artifact_type="watchlist",
            path="artifacts/watchlist.json",
            summary="Daily shortlist",
            created_at="2026-07-09T01:10:00+00:00",
            source_refs=["candidate_score:FPT:2026-07-09"],
        ),
        root=tmp_path,
    )
    record_warning(workspace, "compact recommended", root=tmp_path)
    record_error(workspace, "stale warehouse snapshot", root=tmp_path)

    updated = resume_workspace(workspace.workspace_id, root=tmp_path)
    archived = archive_workspace(workspace.workspace_id, root=tmp_path)
    events_path = tmp_path / workspace.workspace_id / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]

    assert updated.recent_inputs[-1].redaction_status == "redacted"
    assert updated.recent_inputs[-1].summary.endswith("[REDACTED] compare FPT and HPG")
    assert updated.active_artifacts[-1].artifact_id == "watchlist-1"
    assert updated.warnings[-1] == "compact recommended"
    assert updated.errors[-1] == "stale warehouse snapshot"
    assert archived.status == "archived"
    assert {event["event_type"] for event in events} >= {
        "WORKSPACE_CREATED",
        "WORKSPACE_INPUT_ADDED",
        "WORKSPACE_ARTIFACT_ADDED",
        "WORKSPACE_ERROR",
        "WORKSPACE_ARCHIVED",
    }
