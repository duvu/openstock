from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from vnalpha.workspace_context.models import CompactionResult, WorkspaceState
from vnalpha.workspace_context.observability import emit_workspace_audit_event
from vnalpha.workspace_context.storage import (
    _atomic_write_text,
    append_workspace_event,
    ensure_workspace_layout,
    load_workspace_state,
    resolve_workspace_root,
    save_workspace_state,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _source_refs(state: WorkspaceState) -> list[str]:
    refs: list[str] = []
    for artifact in state.active_artifacts:
        refs.extend(artifact.source_refs)
    for task in state.open_tasks:
        refs.extend(task.source_refs)
    deduped: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            deduped.append(ref)
    return deduped[:20]


def _render_compact_markdown(state: WorkspaceState, generated_at: str) -> str:
    sources = _source_refs(state)
    findings = [
        artifact
        for artifact in state.active_artifacts
        if artifact.artifact_type != "decision"
    ]
    decisions = [
        artifact
        for artifact in state.active_artifacts
        if artifact.artifact_type == "decision"
    ]
    lines = [
        "# Compact Workspace Summary",
        "",
        f"Workspace ID: `{state.workspace_id}`",
        f"Title: {state.title}",
        f"Mode: {state.mode}",
        f"Generated At: {generated_at}",
        "",
        "## Active Date",
        f"- {state.active_date or 'None'}",
        "",
        "## Current Goal",
        f"- Continue workspace: {state.title}",
        "",
        "## Active Symbols",
        *([f"- `{symbol}`" for symbol in state.active_symbols[:20]] or ["- None"]),
        "",
        "## Findings",
        *(
            [f"- {artifact.summary} (`{artifact.path}`)" for artifact in findings[:20]]
            or ["- None"]
        ),
        "",
        "## Assumptions",
        *([f"- {assumption}" for assumption in state.assumptions] or ["- None"]),
        "",
        "## Decisions",
        *(
            [f"- {artifact.summary} (`{artifact.path}`)" for artifact in decisions[:20]]
            or ["- None"]
        ),
        "",
        "## Open Tasks",
        *([f"- {task.text}" for task in state.open_tasks] or ["- None"]),
        "",
        "## Warnings",
        *([f"- {warning}" for warning in state.warnings[:20]] or ["- None"]),
        "",
        "## Errors",
        *([f"- {error}" for error in state.errors[:20]] or ["- None"]),
        "",
        "## Recent Inputs",
        *([f"- {item.summary}" for item in state.recent_inputs[:20]] or ["- None"]),
        "",
        "## Source References",
        *([f"- {ref}" for ref in sources] or ["- None"]),
        "",
    ]
    return "\n".join(lines)


def compact_workspace(
    workspace_id: str, *, root: Path | None = None
) -> CompactionResult:
    resolved_root = resolve_workspace_root(root)
    paths = ensure_workspace_layout(root=resolved_root, workspace_id=workspace_id)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    before_size = dict(state.context_size)
    generated_at = _now_iso()
    compact_text = _render_compact_markdown(state, generated_at)
    _atomic_write_text(paths.compact_path, compact_text)
    updated_state = WorkspaceState.from_dict(
        {
            **state.to_dict(),
            "updated_at": generated_at,
            "last_compacted_at": generated_at,
        }
    )
    save_workspace_state(root=resolved_root, state=updated_state)
    append_workspace_event(
        root=resolved_root,
        workspace_id=workspace_id,
        event={
            "event_id": f"evt-{generated_at}",
            "event_type": "WORKSPACE_COMPACTED",
            "workspace_id": workspace_id,
            "created_at": generated_at,
            "metadata": {"summary_lines": len(compact_text.splitlines())},
        },
    )
    emit_workspace_audit_event(
        event_type="WORKSPACE_COMPACTED",
        workspace_id=workspace_id,
        summary="Workspace compacted",
        metadata={"summary_lines": len(compact_text.splitlines())},
    )

    return CompactionResult(
        workspace_id=workspace_id,
        compact_path="compact.md",
        before_size=before_size,
        after_size={"summary_lines": len(compact_text.splitlines())},
        preserved_items=["active_symbols", "open_tasks", "warnings", "recent_inputs"],
        archived_items=[],
        warnings=[],
        generated_at=generated_at,
    )
