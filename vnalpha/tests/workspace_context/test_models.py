from __future__ import annotations

import json

from vnalpha.workspace_context.models import (
    CleanPlan,
    CleanResult,
    CompactionResult,
    ExportResult,
    WorkspaceArtifactRef,
    WorkspaceInputRef,
    WorkspaceState,
    WorkspaceStatusReport,
    WorkspaceTask,
)


def test_workspace_state_round_trip_serialization() -> None:
    state = WorkspaceState(
        workspace_id="ws-20260709-001",
        title="FPT continuation",
        status="active",
        mode="symbol-analysis",
        created_at="2026-07-09T01:02:03+00:00",
        updated_at="2026-07-09T02:03:04+00:00",
        active_date="2026-07-08",
        active_symbols=["FPT", "HPG"],
        active_artifacts=[
            WorkspaceArtifactRef(
                artifact_id="watchlist-latest",
                artifact_type="watchlist",
                path="artifacts/watchlist.json",
                summary="Latest watchlist snapshot",
                created_at="2026-07-09T01:10:00+00:00",
                source_refs=["candidate_score:FPT:2026-07-08"],
                metadata={"rows": 12},
                pinned=True,
            )
        ],
        recent_inputs=[
            WorkspaceInputRef(
                input_id="input-1",
                input_kind="user",
                summary="Compare FPT and HPG for trend quality",
                redaction_status="redacted",
                created_at="2026-07-09T01:11:00+00:00",
                source="tui",
                content="Compare FPT and HPG for trend quality",
                metadata={"length": 37},
            )
        ],
        open_tasks=[
            WorkspaceTask(
                task_id="task-1",
                text="Review watchlist leaders",
                status="open",
                priority="high",
                created_at="2026-07-09T01:12:00+00:00",
                updated_at="2026-07-09T01:12:00+00:00",
                source_refs=["artifacts/watchlist.json"],
            )
        ],
        assumptions=["Fresh warehouse data should override stale summaries."],
        warnings=["compact recommended"],
        errors=[],
        data_freshness={"warehouse": "fresh", "compact": "stale"},
        last_compacted_at="2026-07-09T00:00:00+00:00",
        context_size={"events": 4, "inputs": 1},
    )

    payload = state.to_dict()

    assert payload["workspace_id"] == "ws-20260709-001"
    assert payload["active_artifacts"][0]["artifact_type"] == "watchlist"
    assert payload["recent_inputs"][0]["redaction_status"] == "redacted"

    restored = WorkspaceState.from_dict(json.loads(json.dumps(payload)))

    assert restored == state
    assert restored.active_artifacts[0].metadata["rows"] == 12
    assert restored.open_tasks[0].source_refs == ["artifacts/watchlist.json"]


def test_workspace_report_models_round_trip() -> None:
    report = WorkspaceStatusReport(
        workspace_id="ws-20260709-001",
        title="FPT continuation",
        mode="symbol-analysis",
        status="active",
        active_date="2026-07-08",
        active_symbols=["FPT"],
        open_tasks=["Review breakout evidence"],
        warnings=["compact recommended"],
        errors=["stale context"],
        last_updated_at="2026-07-09T02:03:04+00:00",
        last_compacted_at="2026-07-09T00:00:00+00:00",
        context_size={"events": 8},
        stale_artifacts=["artifacts/watchlist.json"],
        suggested_action="/context compact",
        source_refs=["workspace.json", "events.jsonl#evt-1"],
    )
    compaction = CompactionResult(
        workspace_id="ws-20260709-001",
        compact_path="compact.md",
        before_size={"events": 8},
        after_size={"summary_lines": 20},
        preserved_items=["active_symbols", "open_tasks"],
        archived_items=["duplicate outputs"],
        warnings=["none"],
        generated_at="2026-07-09T02:10:00+00:00",
    )
    clean_plan = CleanPlan(
        workspace_id="ws-20260709-001",
        dry_run=True,
        archive_first=True,
        keep=["workspace.json", "compact.md"],
        archive=["events.old.jsonl"],
        remove=["artifacts/tmp.txt"],
        needs_confirmation=["notes/private.md"],
        protected=["audit.jsonl"],
        summary="dry run only",
    )
    clean_result = CleanResult(
        workspace_id="ws-20260709-001",
        dry_run=True,
        archived=["archive/events.old.jsonl"],
        removed=[],
        kept=["workspace.json"],
        warnings=["notes skipped"],
        generated_at="2026-07-09T02:20:00+00:00",
        plan=clean_plan,
    )
    export_result = ExportResult(
        workspace_id="ws-20260709-001",
        bundle_dir="exports/20260709T022500-context-bundle",
        manifest_path="exports/20260709T022500-context-bundle/manifest.json",
        exported_files=["manifest.json", "workspace.json", "context.md"],
        checksums={"workspace.json": "abc123"},
        generated_at="2026-07-09T02:25:00+00:00",
    )

    assert WorkspaceStatusReport.from_dict(report.to_dict()) == report
    assert CompactionResult.from_dict(compaction.to_dict()) == compaction
    assert CleanPlan.from_dict(clean_plan.to_dict()) == clean_plan
    assert CleanResult.from_dict(clean_result.to_dict()) == clean_result
    assert ExportResult.from_dict(export_result.to_dict()) == export_result
