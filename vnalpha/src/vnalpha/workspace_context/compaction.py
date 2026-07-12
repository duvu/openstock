from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from vnalpha.model_routing.models import ModelTaskType
from vnalpha.workspace_context.locking import workspace_transaction
from vnalpha.workspace_context.models import CompactionResult, WorkspaceState
from vnalpha.workspace_context.observability import emit_workspace_audit_event
from vnalpha.workspace_context.retention import enforce_retention
from vnalpha.workspace_context.storage import (
    _atomic_write_text,
    append_workspace_event,
    load_workspace_state,
    resolve_workspace_root,
    save_workspace_state,
)

if TYPE_CHECKING:
    from vnalpha.assistant.gateway import LLMGatewayClient


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
        *([f"- {item.summary}" for item in state.recent_inputs[-20:]] or ["- None"]),
        "",
        "## Source References",
        *([f"- {ref}" for ref in sources] or ["- None"]),
        "",
    ]
    return "\n".join(lines)


def _llm_compact(
    llm_client: LLMGatewayClient,
    deterministic_summary: str,
    state: WorkspaceState,
) -> tuple[str, dict]:
    messages = [
        {
            "role": "system",
            "content": (
                "Compact the supplied workspace summary without inventing facts. "
                "Preserve objective, symbols, findings, assumptions, open tasks, warnings, "
                "errors, and source references. Return Markdown only."
            ),
        },
        {"role": "user", "content": deterministic_summary},
    ]
    text, usage = llm_client.chat(
        messages,
        stage="compact",
        task_type=ModelTaskType.WORKSPACE_COMPACTION.value,
        route_metadata={
            "workspace_id": state.workspace_id,
            "artifact_count": len(state.active_artifacts),
            "context_bytes": len(deterministic_summary.encode("utf-8")),
        },
    )
    compact_text = text.strip()
    if not compact_text:
        raise ValueError("LLM returned an empty workspace summary.")
    if not compact_text.startswith("#"):
        compact_text = "# Compact Workspace Summary\n\n" + compact_text
    return compact_text, usage


def compact_workspace(
    workspace_id: str,
    *,
    root: Path | None = None,
    llm_client: LLMGatewayClient | None = None,
) -> CompactionResult:
    resolved_root = resolve_workspace_root(root)
    with workspace_transaction(workspace_id, root=resolved_root) as paths:
        state = load_workspace_state(root=resolved_root, workspace_id=workspace_id)
        before_size = dict(state.context_size)
        generated_at = _now_iso()
        deterministic_summary = _render_compact_markdown(state, generated_at)
        compact_text = deterministic_summary
        warnings: list[str] = []
        model_route: dict | None = None
        if llm_client is not None:
            try:
                compact_text, usage = _llm_compact(
                    llm_client, deterministic_summary, state
                )
                route = usage.get("model_route") if isinstance(usage, dict) else None
                model_route = dict(route) if isinstance(route, dict) else None
            except Exception as exc:
                warnings.append(
                    f"LLM compaction failed; deterministic summary used instead: {exc}"
                )

        _atomic_write_text(paths.compact_path, compact_text)
        updated_state = WorkspaceState.from_dict(
            {
                **state.to_dict(),
                "updated_at": generated_at,
                "last_compacted_at": generated_at,
            }
        )
        retention = enforce_retention(root=resolved_root, state=updated_state)
        retained_state = retention.state
        save_workspace_state(root=resolved_root, state=retained_state)
        event_metadata: dict = {
            "summary_lines": len(compact_text.splitlines()),
            "archived_counts": retention.archived_counts,
        }
        if model_route is not None:
            event_metadata["model_route"] = model_route
        append_workspace_event(
            root=resolved_root,
            workspace_id=workspace_id,
            event={
                "event_id": f"evt-{generated_at}",
                "event_type": "WORKSPACE_COMPACTED",
                "workspace_id": workspace_id,
                "created_at": generated_at,
                "metadata": event_metadata,
            },
        )
        emit_workspace_audit_event(
            event_type="WORKSPACE_COMPACTED",
            workspace_id=workspace_id,
            summary="Workspace compacted",
            metadata={"summary_lines": len(compact_text.splitlines())},
        )

        after_size = dict(retained_state.context_size)
        after_size["summary_lines"] = len(compact_text.splitlines())
        return CompactionResult(
            workspace_id=workspace_id,
            compact_path="compact.md",
            before_size=before_size,
            after_size=after_size,
            preserved_items=[
                "active_symbols",
                "open_tasks",
                "warnings",
                "recent_inputs",
            ],
            archived_items=[
                f"{name}:{count}"
                for name, count in sorted(retention.archived_counts.items())
            ],
            warnings=warnings,
            generated_at=generated_at,
        )
