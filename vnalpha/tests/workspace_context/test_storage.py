from __future__ import annotations

from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.storage import (
    resolve_workspace_root,
)


def _sample_state() -> WorkspaceState:
    return WorkspaceState(
        workspace_id="ws-20260709-001",
        title="Test workspace",
        status="active",
        mode="research",
        created_at="2026-07-09T01:02:03+00:00",
        updated_at="2026-07-09T01:02:03+00:00",
        active_date="2026-07-09",
        active_symbols=["FPT"],
        assumptions=["Fresh warehouse data remains authoritative."],
    )


def test_resolve_workspace_root_prefers_env_override(monkeypatch, tmp_path) -> None:
    override = tmp_path / "custom-root"
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(override))

    resolved = resolve_workspace_root()

    assert resolved == override
