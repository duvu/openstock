from __future__ import annotations

import json

from vnalpha.workspace_context.recovery import recover_workspace


def test_recovery_quarantines_malformed_workspace_and_keeps_startup_available(
    tmp_path,
):
    workspace_dir = tmp_path / "ws-broken"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "workspace.json").write_text("{broken", encoding="utf-8")
    (tmp_path / "latest.json").write_text(
        json.dumps({"workspace_id": "ws-broken"}), encoding="utf-8"
    )

    result = recover_workspace(tmp_path)

    assert result.workspace.status == "active"
    assert result.warnings
    assert result.quarantined_paths
    assert not (workspace_dir / "workspace.json").exists()
    assert list((tmp_path / "archive" / "quarantine").iterdir())
