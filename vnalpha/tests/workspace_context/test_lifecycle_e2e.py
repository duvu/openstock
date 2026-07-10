from __future__ import annotations

import json
from pathlib import Path

from vnalpha.workspace_context.compaction import compact_workspace
from vnalpha.workspace_context.export import export_workspace
from vnalpha.workspace_context.integration import (
    FRESHNESS_CAVEAT,
    MAX_ASSISTANT_CONTEXT_CHARS,
    build_workspace_context_prompt_prefix,
)
from vnalpha.workspace_context.lifecycle import (
    get_status,
    new_workspace,
    record_input,
    resume_workspace,
)
from vnalpha.workspace_context.storage import ensure_workspace_layout


def test_workspace_context_lifecycle_preserves_safe_resumable_boundaries(
    tmp_path: Path,
) -> None:
    # Given: an isolated workspace root and an unrelated audit log sentinel.
    workspace_root = tmp_path / "workspaces"
    external_audit_path = tmp_path / "audit.jsonl"
    external_audit_text = "EXTERNAL_AUDIT_SENTINEL\n"
    external_audit_path.write_text(external_audit_text, encoding="utf-8")
    raw_secret = "lifecycle-raw-secret"
    raw_event = "RAW_EVENT_STREAM_CONTENT"

    # When: a workspace follows the new -> input -> compact -> status -> export -> new -> resume lifecycle.
    previous = new_workspace(root=workspace_root)
    record_input(
        previous,
        f"api_key={raw_secret} compare FPT and HPG",
        "user",
        root=workspace_root,
    )
    paths = ensure_workspace_layout(
        root=workspace_root, workspace_id=previous.workspace_id
    )
    paths.events_path.write_text(raw_event, encoding="utf-8")
    compact_workspace(previous.workspace_id, root=workspace_root)
    status = get_status(previous.workspace_id, root=workspace_root)
    prefix = build_workspace_context_prompt_prefix(
        previous.workspace_id, root=workspace_root
    )
    exported = export_workspace(previous.workspace_id, root=workspace_root)
    current = new_workspace(root=workspace_root)
    resumed = resume_workspace(previous.workspace_id, root=workspace_root)

    # Then: sensitive input and raw events stay outside persistent and assistant-facing context.
    state_text = paths.workspace_json_path.read_text(encoding="utf-8")
    assert raw_secret not in state_text
    assert "[REDACTED]" in state_text
    assert raw_event not in prefix
    assert len(prefix) <= MAX_ASSISTANT_CONTEXT_CHARS
    assert FRESHNESS_CAVEAT in prefix

    # Then: the status and export describe only the workspace's selected, safe bundle.
    assert status.workspace_id == previous.workspace_id
    assert status.last_compacted_at is not None
    manifest = json.loads(Path(exported.manifest_path).read_text(encoding="utf-8"))
    bundle_dir = Path(exported.bundle_dir)
    bundle_files = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file()
    }
    selected_content = "\n".join(
        (bundle_dir / filename).read_text(encoding="utf-8")
        for filename in exported.exported_files
    )
    assert "events.jsonl" not in manifest["files"]
    assert "audit.jsonl" not in manifest["files"]
    assert "events.jsonl" not in bundle_files
    assert "audit.jsonl" not in bundle_files
    assert raw_event not in selected_content
    assert raw_secret not in selected_content

    # Then: creating a successor archives but does not erase the old workspace or external audit log.
    assert current.workspace_id != previous.workspace_id
    assert resumed.workspace_id == previous.workspace_id
    assert resumed.status == "archived"
    assert external_audit_path.read_text(encoding="utf-8") == external_audit_text
