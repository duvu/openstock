from __future__ import annotations

from vnalpha.tui.runtime_status import RuntimeState, RuntimeStatus
from vnalpha.tui.widgets.output_stream import OutputStream
from vnalpha.tui.widgets.status_bar import StatusBar
from vnalpha.workspace_context.lifecycle import (
    get_or_create_latest_workspace,
    get_resume_summary,
)
from vnalpha.workspace_context.models import WorkspaceResumeSummary, WorkspaceState


def initialize_workspace() -> tuple[WorkspaceState, WorkspaceResumeSummary]:
    workspace = get_or_create_latest_workspace()
    return workspace, get_resume_summary(workspace.workspace_id)


def resume_summary_for(workspace: WorkspaceState) -> WorkspaceResumeSummary:
    return get_resume_summary(workspace.workspace_id)


def render_workspace_resume(
    summary: WorkspaceResumeSummary,
    status_bar: StatusBar,
    output: OutputStream,
) -> None:
    status_bar.update_status(
        RuntimeStatus(
            state=RuntimeState.READY,
            label=f"ws={summary.workspace_id}",
            detail=(
                f"mode={summary.mode} symbols={len(summary.active_symbols)} "
                f"tasks={summary.open_task_count}"
            ),
        )
    )
    output.show_assistant_message(
        "\n".join(
            [
                f"Workspace resumed: {summary.title} ({summary.workspace_id})",
                (
                    f"mode={summary.mode} date={summary.active_date or 'none'} "
                    f"symbols={len(summary.active_symbols)} "
                    f"tasks={summary.open_task_count}"
                ),
            ]
        ),
        style="dim",
    )
