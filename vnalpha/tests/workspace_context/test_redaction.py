from __future__ import annotations

from vnalpha.workspace_context.models import WorkspaceArtifactRef, WorkspaceState
from vnalpha.workspace_context.redaction import redact_workspace_text
from vnalpha.workspace_context.storage import load_workspace_state, save_workspace_state


def test_workspace_redaction_reports_text_status_and_categories() -> None:
    value = redact_workspace_text("api_key=secret password=hidden compare FPT")

    assert value.text == "api_key=[REDACTED] password=[REDACTED] compare FPT"
    assert value.status == "redacted"
    assert value.matched_categories == ("api_key", "password")


def test_workspace_artifact_metadata_is_redacted_on_save(tmp_path) -> None:
    state = WorkspaceState(
        workspace_id="ws-redaction",
        title="Research",
        status="active",
        mode="research",
        created_at="2026-07-12T00:00:00+00:00",
        updated_at="2026-07-12T00:00:00+00:00",
        active_artifacts=[
            WorkspaceArtifactRef(
                artifact_id="artifact-1",
                artifact_type="report",
                path="artifacts/report.md",
                summary="api_key=summary-secret",
                created_at="2026-07-12T00:00:00+00:00",
                metadata={"password": "metadata-secret"},
            )
        ],
    )

    save_workspace_state(root=tmp_path, state=state)
    loaded = load_workspace_state(root=tmp_path, workspace_id=state.workspace_id)

    assert loaded.active_artifacts[0].summary == "api_key=[REDACTED]"
    assert loaded.active_artifacts[0].metadata["password"] == "[REDACTED]"
