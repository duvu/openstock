from __future__ import annotations

import json

import pytest

import vnalpha.workspace_context.persistence as persistence_module
from vnalpha.workspace_context import lifecycle
from vnalpha.workspace_context.lifecycle import (
    archive_workspace,
    check_lifecycle_invariants,
    create_workspace,
    get_or_create_latest_workspace,
    get_status,
    list_workspaces,
    reactivate_workspace,
    record_artifact,
    record_error,
    record_input,
    record_warning,
    resume_workspace,
)
from vnalpha.workspace_context.models import WorkspaceArtifactRef, WorkspaceState
from vnalpha.workspace_context.storage import (
    load_latest_workspace_id,
    save_workspace_state,
)


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
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]

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


def test_record_input_never_persists_raw_sensitive_content(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_LOG_CONTENT_MODE", "full")
    workspace = create_workspace(root=tmp_path)

    record_input(
        workspace,
        "api_key=top-secret compare FPT",
        "user",
        root=tmp_path,
    )

    saved = resume_workspace(workspace.workspace_id, root=tmp_path)
    input_ref = saved.recent_inputs[-1]
    assert "top-secret" not in input_ref.summary
    assert "top-secret" not in (input_ref.content or "")
    assert input_ref.redaction_status == "redacted"


def test_new_workspace_compacts_archives_and_keeps_old_workspace_resumable(
    tmp_path,
) -> None:
    previous = create_workspace(title="FPT research", mode="research", root=tmp_path)
    record_input(
        previous,
        "api_key=top-secret compare FPT and HPG",
        "user",
        root=tmp_path,
    )

    current = lifecycle.new_workspace(root=tmp_path)
    resumed = reactivate_workspace(previous.workspace_id, root=tmp_path)
    previous_events = (tmp_path / previous.workspace_id / "events.jsonl").read_text(
        encoding="utf-8"
    )

    assert current.workspace_id != previous.workspace_id
    assert current.status == "active"
    assert (tmp_path / previous.workspace_id / "compact.md").exists()
    assert resumed.status == "active"
    assert load_latest_workspace_id(root=tmp_path) == previous.workspace_id
    assert "WORKSPACE_REACTIVATED" in previous_events
    assert "top-secret" not in previous_events


def test_new_workspace_skips_compaction_only_when_requested(tmp_path) -> None:
    previous = create_workspace(root=tmp_path)

    lifecycle.new_workspace(no_compact=True, root=tmp_path)

    assert not (tmp_path / previous.workspace_id / "compact.md").exists()
    assert reactivate_workspace(previous.workspace_id, root=tmp_path).status == "active"


def test_new_workspace_emits_workspace_and_audit_events(tmp_path, monkeypatch) -> None:
    audit_events: list[tuple[str, str, str, dict[str, str | int | float | bool]]] = []

    def record_audit_event(
        *,
        event_type: str,
        workspace_id: str,
        summary: str,
        metadata: dict[str, str | int | float | bool],
    ) -> None:
        audit_events.append((event_type, workspace_id, summary, metadata))

    monkeypatch.setattr(
        persistence_module, "emit_workspace_audit_event", record_audit_event
    )
    create_workspace(root=tmp_path)

    current = lifecycle.new_workspace(no_compact=True, root=tmp_path)

    events = [
        json.loads(line)
        for line in (tmp_path / current.workspace_id / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert any(event["event_type"] == "WORKSPACE_NEW_STARTED" for event in events)
    assert any(
        event_type == "WORKSPACE_NEW_STARTED" and workspace_id == current.workspace_id
        for event_type, workspace_id, _, _ in audit_events
    )


def test_resume_summary_and_list_are_structured_and_deterministic(tmp_path) -> None:
    first = create_workspace(title="First", mode="research", root=tmp_path)
    second = create_workspace(title="Second", mode="watchlist", root=tmp_path)
    save_workspace_state(
        root=tmp_path,
        state=WorkspaceState.from_dict(
            {
                **first.to_dict(),
                "updated_at": "2026-07-09T00:00:00+00:00",
            }
        ),
    )
    save_workspace_state(
        root=tmp_path,
        state=WorkspaceState.from_dict(
            {
                **second.to_dict(),
                "updated_at": "2026-07-10T00:00:00+00:00",
            }
        ),
    )

    summary = lifecycle.get_resume_summary(second.workspace_id, root=tmp_path)
    listed = lifecycle.list_workspaces(root=tmp_path)

    assert summary.workspace_id == second.workspace_id
    assert summary.title == "Second"
    assert [item.workspace_id for item in listed] == [
        second.workspace_id,
        first.workspace_id,
    ]
    assert all(
        {"workspace_id", "title", "mode", "status", "updated_at"}
        <= item.to_dict().keys()
        for item in listed
    )


def test_status_reports_missing_artifacts_and_context_threshold(tmp_path) -> None:
    workspace = create_workspace(root=tmp_path)
    record_artifact(
        workspace,
        WorkspaceArtifactRef(
            artifact_id="missing-artifact",
            artifact_type="report",
            path="artifacts/missing.json",
            summary="Missing report",
            created_at="2026-07-09T00:00:00+00:00",
        ),
        root=tmp_path,
    )
    state = resume_workspace(workspace.workspace_id, root=tmp_path)
    save_workspace_state(
        root=tmp_path,
        state=WorkspaceState.from_dict(
            {
                **state.to_dict(),
                "context_size": {"events": 100, "inputs": 50, "artifacts": 50},
            }
        ),
    )

    report = get_status(workspace.workspace_id, root=tmp_path)

    assert report.stale_artifacts == ["missing-artifact"]
    assert report.suggested_action == "/context compact"


def test_workspace_events_exclude_raw_user_text(tmp_path) -> None:
    workspace = create_workspace(title="api_key=top-secret", root=tmp_path)
    record_warning(workspace, "api_key=top-secret", root=tmp_path)
    record_error(workspace, "api_key=top-secret", root=tmp_path)

    events = (tmp_path / workspace.workspace_id / "events.jsonl").read_text(
        encoding="utf-8"
    )

    assert "top-secret" not in events


def test_archive_clears_latest_and_resume_requires_reactivation(tmp_path) -> None:
    workspace = create_workspace(root=tmp_path)

    archived = archive_workspace(workspace.workspace_id, root=tmp_path)

    assert archived.status == "archived"
    assert load_latest_workspace_id(root=tmp_path) is None
    with pytest.raises(lifecycle.WorkspaceLifecycleError):
        resume_workspace(workspace.workspace_id, root=tmp_path)

    reactivated = reactivate_workspace(workspace.workspace_id, root=tmp_path)

    assert reactivated.status == "active"
    assert load_latest_workspace_id(root=tmp_path) == workspace.workspace_id


def test_get_status_does_not_mutate_latest_or_events(tmp_path) -> None:
    workspace = create_workspace(root=tmp_path)
    events_path = tmp_path / workspace.workspace_id / "events.jsonl"
    before = events_path.read_text(encoding="utf-8")

    report = get_status(workspace.workspace_id, root=tmp_path)

    assert report.workspace_id == workspace.workspace_id
    assert load_latest_workspace_id(root=tmp_path) == workspace.workspace_id
    assert events_path.read_text(encoding="utf-8") == before


def test_corrupt_latest_pointer_recovers_to_a_new_active_workspace(tmp_path) -> None:
    (tmp_path / "latest.json").write_text("{broken", encoding="utf-8")

    workspace = get_or_create_latest_workspace(root=tmp_path)

    assert workspace.status == "active"
    assert load_latest_workspace_id(root=tmp_path) == workspace.workspace_id
    assert list((tmp_path / "archive" / "quarantine").glob("latest-*.json"))


def test_lifecycle_invariants_require_one_active_latest_workspace(tmp_path) -> None:
    workspace = create_workspace(root=tmp_path)
    clear_latest = tmp_path / "latest.json"
    clear_latest.unlink()

    with pytest.raises(lifecycle.WorkspaceLifecycleError):
        check_lifecycle_invariants(root=tmp_path)

    save_workspace_state(
        root=tmp_path,
        state=WorkspaceState.from_dict(
            {
                **workspace.to_dict(),
                "status": "archived",
            }
        ),
    )
    check_lifecycle_invariants(root=tmp_path)
