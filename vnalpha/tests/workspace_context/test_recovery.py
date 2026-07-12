from __future__ import annotations

import json

import vnalpha.workspace_context.recovery as recovery_module
from vnalpha.workspace_context.recovery import inspect_workspace, recover_workspace


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


def test_recovery_dry_run_inspection_does_not_move_malformed_files(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text("{broken", encoding="utf-8")

    invalid = inspect_workspace(tmp_path)

    assert invalid == (str(path),)
    assert path.exists()


def test_recovery_uses_temporary_workspace_when_canonical_root_is_unavailable(
    tmp_path, monkeypatch
):
    def unavailable(*, root):
        raise OSError("permission denied")

    monkeypatch.setattr(recovery_module, "get_or_create_latest_workspace", unavailable)

    result = recover_workspace(tmp_path)

    assert result.temporary is True
    assert result.workspace.status == "temporary"
    assert result.warnings
