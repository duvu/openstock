from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from vnalpha.workspace_context.models import CompactionResult, WorkspaceState
from vnalpha.workspace_context.storage import (
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
    return deduped


def _render_compact_markdown(state: WorkspaceState) -> str:
    sources = _source_refs(state)
    lines = [
        "# Compact Workspace Summary",
        "",
        f"Workspace ID: `{state.workspace_id}`",
        f"Title: {state.title}",
        f"Mode: {state.mode}",
        "",
        "## Current Goal",
        f"- Continue workspace: {state.title}",
        "",
        "## Active Symbols",
        *([f"- `{symbol}`" for symbol in state.active_symbols] or ["- None"]),
        "",
        "## Findings",
        *(
            [
                f"- {artifact.summary} (`{artifact.path}`)"
                for artifact in state.active_artifacts
            ]
            or ["- None"]
        ),
        "",
        "## Assumptions",
        *([f"- {assumption}" for assumption in state.assumptions] or ["- None"]),
        "",
        "## Decisions",
        *([f"- {warning}" for warning in state.warnings] or ["- None"]),
        "",
        "## Open Tasks",
        *([f"- {task.text}" for task in state.open_tasks] or ["- None"]),
        "",
        "## Warnings",
        *([f"- {warning}" for warning in state.warnings] or ["- None"]),
        "",
        "## Recent Inputs",
        *([f"- {item.summary}" for item in state.recent_inputs] or ["- None"]),
        "",
        "## Source References",
        *([f"- {ref}" for ref in sources] or ["- None"]),
        "",
    ]
    return "\n".join(lines)


def compact_workspace(workspace_id: str, *, root: Path | None = None) -> CompactionResult:
    resolved_root = resolve_workspace_root(root)
    paths = ensure_workspace_layout(root=resolved_root, workspace_id=workspace_id)
    state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
    before_size = dict(state.context_size)
    compact_text = _render_compact_markdown(state)
    paths.compact_path.write_text(compact_text, encoding="utf-8")

    generated_at = _now_iso()
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
