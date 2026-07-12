from __future__ import annotations

import hashlib

import pytest

from vnalpha.workspace_context.lifecycle import create_workspace
from vnalpha.workspace_context.migration import (
    WorkspaceMigrationConflictError,
    detect_legacy_workspace_roots,
    migrate_legacy_workspaces,
)
from vnalpha.workspace_context.storage import load_latest_workspace_id


def test_detect_legacy_workspace_root_when_canonical_is_empty(tmp_path) -> None:
    legacy_root = tmp_path / ".vnalpha" / "workspaces"
    canonical_root = tmp_path / "state" / "openstock" / "workspaces"
    create_workspace(root=legacy_root)

    roots = detect_legacy_workspace_roots(
        canonical_root=canonical_root,
        cwd=tmp_path,
    )

    assert roots == (legacy_root,)


def test_migrate_legacy_workspace_preserves_backup_and_latest_pointer(tmp_path) -> None:
    legacy_root = tmp_path / ".vnalpha" / "workspaces"
    canonical_root = tmp_path / "state" / "openstock" / "workspaces"
    workspace = create_workspace(title="Legacy", root=legacy_root)
    source_file = legacy_root / workspace.workspace_id / "workspace.json"
    source_checksum = hashlib.sha256(source_file.read_bytes()).hexdigest()

    result = migrate_legacy_workspaces(
        source_root=legacy_root,
        destination_root=canonical_root,
    )

    assert result.workspace_ids == (workspace.workspace_id,)
    assert load_latest_workspace_id(root=canonical_root) == workspace.workspace_id
    assert (canonical_root / workspace.workspace_id / "workspace.json").exists()
    backup_file = (
        canonical_root / result.backup_root / workspace.workspace_id / "workspace.json"
    )
    assert backup_file.exists()
    assert hashlib.sha256(backup_file.read_bytes()).hexdigest() == source_checksum


def test_migration_rejects_multiple_detected_legacy_roots(tmp_path) -> None:
    first_root = tmp_path / ".vnalpha" / "workspaces"
    second_root = tmp_path / "vnalpha" / ".vnalpha" / "workspaces"
    canonical_root = tmp_path / "state" / "openstock" / "workspaces"
    create_workspace(root=first_root)
    create_workspace(root=second_root)

    with pytest.raises(WorkspaceMigrationConflictError):
        migrate_legacy_workspaces(
            destination_root=canonical_root,
            cwd=tmp_path,
        )


def test_migration_rejects_occupied_destination(tmp_path) -> None:
    legacy_root = tmp_path / ".vnalpha" / "workspaces"
    canonical_root = tmp_path / "state" / "openstock" / "workspaces"
    create_workspace(root=legacy_root)
    create_workspace(root=canonical_root)

    with pytest.raises(WorkspaceMigrationConflictError):
        migrate_legacy_workspaces(
            source_root=legacy_root,
            destination_root=canonical_root,
        )


def test_migration_rerun_is_idempotent_for_same_source(tmp_path) -> None:
    legacy_root = tmp_path / ".vnalpha" / "workspaces"
    canonical_root = tmp_path / "state" / "openstock" / "workspaces"
    create_workspace(root=legacy_root)

    first = migrate_legacy_workspaces(
        source_root=legacy_root,
        destination_root=canonical_root,
    )
    second = migrate_legacy_workspaces(
        source_root=legacy_root,
        destination_root=canonical_root,
    )

    assert second.workspace_ids == first.workspace_ids
    assert second.backup_root == first.backup_root


def test_migration_rejects_symlinked_legacy_content(tmp_path) -> None:
    legacy_root = tmp_path / ".vnalpha" / "workspaces"
    canonical_root = tmp_path / "state" / "openstock" / "workspaces"
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    workspace = create_workspace(root=legacy_root)
    (legacy_root / workspace.workspace_id / "outside.txt").symlink_to(outside)

    with pytest.raises(WorkspaceMigrationConflictError):
        migrate_legacy_workspaces(
            source_root=legacy_root,
            destination_root=canonical_root,
        )
