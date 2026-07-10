from __future__ import annotations

from pathlib import Path
from typing import Final

from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.storage import (
    COMPACT_MD_NAME,
    WORKSPACE_JSON_NAME,
    _atomic_write_text,
    ensure_workspace_layout,
    load_workspace_state,
    resolve_workspace_root,
)

MAX_ASSISTANT_CONTEXT_CHARS: Final = 6_000
MAX_ASSISTANT_CONTEXT_ITEMS: Final = 10
MAX_COMPACT_CHARS: Final = 3_000
FRESHNESS_CAVEAT: Final = (
    "Freshness caveat: Current warehouse and tool output is authoritative; "
    "workspace summaries may be stale."
)


def render_context_markdown(state: WorkspaceState) -> str:
    lines = [
        "# Workspace Context",
        "",
        f"Workspace ID: `{state.workspace_id}`",
        f"Title: {state.title}",
        f"Status: {state.status}",
        f"Mode: {state.mode}",
    ]
    if state.active_date:
        lines.append(f"Active Date: {state.active_date}")
    lines.extend(["", "## Active Symbols"])
    lines.extend([f"- `{symbol}`" for symbol in state.active_symbols] or ["- None"])
    lines.extend(["", "## Open Tasks"])
    lines.extend([f"- {task.text}" for task in state.open_tasks] or ["- None"])
    lines.extend(["", "## Recent Inputs"])
    lines.extend([f"- {item.summary}" for item in state.recent_inputs] or ["- None"])
    lines.extend(["", "## Artifacts"])
    lines.extend(
        [f"- {item.summary} (`{item.path}`)" for item in state.active_artifacts]
        or ["- None"]
    )
    lines.extend(["", "## Assumptions"])
    lines.extend([f"- {item}" for item in state.assumptions] or ["- None"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {item}" for item in state.warnings] or ["- None"])
    lines.append("")
    return "\n".join(lines)


def write_context_markdown(state: WorkspaceState, *, root: Path | None = None) -> Path:
    resolved_root = resolve_workspace_root(root)
    paths = ensure_workspace_layout(root=resolved_root, workspace_id=state.workspace_id)
    _atomic_write_text(paths.context_path, render_context_markdown(state))
    return paths.context_path


def build_workspace_context_prompt_prefix(
    workspace_id: str, *, root: Path | None = None
) -> str:
    workspace_dir = resolve_workspace_root(root) / workspace_id
    if not (workspace_dir / WORKSPACE_JSON_NAME).exists():
        return ""

    state = load_workspace_state(root=workspace_dir.parent, workspace_id=workspace_id)
    lines = [
        "# Workspace Context",
        FRESHNESS_CAVEAT,
        f"Workspace: {state.title} ({state.status}, {state.mode})",
    ]
    if state.active_date:
        lines.append(f"Active date: {state.active_date}")
    if state.active_symbols:
        lines.append(
            "Active symbols: "
            + ", ".join(state.active_symbols[:MAX_ASSISTANT_CONTEXT_ITEMS])
        )
    if state.open_tasks:
        lines.extend(
            [
                "Open tasks:",
                *[
                    f"- {task.text}"
                    for task in state.open_tasks[:MAX_ASSISTANT_CONTEXT_ITEMS]
                ],
            ]
        )
    if state.active_artifacts:
        lines.extend(
            [
                "Selected artifact summaries:",
                *[
                    f"- {artifact.summary} ({artifact.path})"
                    for artifact in state.active_artifacts[:MAX_ASSISTANT_CONTEXT_ITEMS]
                ],
            ]
        )

    compact_path = workspace_dir / COMPACT_MD_NAME
    if compact_path.exists():
        compact_text = compact_path.read_text(encoding="utf-8")[:MAX_COMPACT_CHARS]
        if compact_text:
            lines.extend(["Compact summary:", compact_text])

    return ("\n".join(lines) + "\n\n")[:MAX_ASSISTANT_CONTEXT_CHARS]
