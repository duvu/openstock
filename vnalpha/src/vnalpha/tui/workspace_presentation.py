from __future__ import annotations

from vnalpha.tui.runtime_status import RuntimeState, RuntimeStatus
from vnalpha.tui.widgets.output_stream import OutputStream
from vnalpha.tui.widgets.status_bar import StatusBar
from vnalpha.workspace_context.lifecycle import get_resume_summary
from vnalpha.workspace_context.models import WorkspaceResumeSummary, WorkspaceState
from vnalpha.workspace_context.recovery import recover_workspace


def initialize_workspace() -> tuple[WorkspaceState, WorkspaceResumeSummary]:
    recovery = recover_workspace()
    workspace = recovery.workspace
    summary = WorkspaceResumeSummary(
        workspace_id=workspace.workspace_id,
        title=workspace.title,
        mode=workspace.mode,
        status=workspace.status,
        active_date=workspace.active_date,
        active_symbols=list(workspace.active_symbols),
        open_task_count=len(workspace.open_tasks),
        last_compacted_at=workspace.last_compacted_at,
        warnings=[*workspace.warnings, *recovery.warnings],
        errors=list(workspace.errors),
    )
    return workspace, summary


def resume_summary_for(workspace: WorkspaceState) -> WorkspaceResumeSummary:
    if workspace.status == "temporary":
        return WorkspaceResumeSummary(
            workspace_id=workspace.workspace_id,
            title=workspace.title,
            mode=workspace.mode,
            status=workspace.status,
            active_date=workspace.active_date,
            active_symbols=list(workspace.active_symbols),
            open_task_count=len(workspace.open_tasks),
            last_compacted_at=workspace.last_compacted_at,
            warnings=list(workspace.warnings),
            errors=list(workspace.errors),
        )
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
