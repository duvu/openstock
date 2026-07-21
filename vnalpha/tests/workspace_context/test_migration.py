from __future__ import annotations

from vnalpha.workspace_context.lifecycle import create_workspace
from vnalpha.workspace_context.migration import (
    detect_legacy_workspace_roots,
)


def test_detect_legacy_workspace_root_when_canonical_is_empty(tmp_path) -> None:
    legacy_root = tmp_path / ".vnalpha" / "workspaces"
    canonical_root = tmp_path / "state" / "openstock" / "workspaces"
    create_workspace(root=legacy_root)

    roots = detect_legacy_workspace_roots(
        canonical_root=canonical_root,
        cwd=tmp_path,
    )

    assert roots == (legacy_root,)
