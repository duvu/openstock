from __future__ import annotations

from pathlib import Path

from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.storage import ensure_workspace_layout, resolve_workspace_root


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
    lines.extend(
        [f"- `{symbol}`" for symbol in state.active_symbols] or ["- None"]
    )
    lines.extend(["", "## Open Tasks"])
    lines.extend([f"- {task.text}" for task in state.open_tasks] or ["- None"])
    lines.extend(["", "## Recent Inputs"])
    lines.extend(
        [f"- {item.summary}" for item in state.recent_inputs] or ["- None"]
    )
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
    paths.context_path.write_text(render_context_markdown(state), encoding="utf-8")
    return paths.context_path
