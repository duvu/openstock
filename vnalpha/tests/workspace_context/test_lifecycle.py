from __future__ import annotations

from vnalpha.workspace_context.lifecycle import (
    create_workspace,
    get_status,
    resume_workspace,
)


def test_create_resume_and_status_flow(tmp_path) -> None:
    workspace = create_workspace(title="FPT workflow", mode="research", root=tmp_path)

    assert workspace.workspace_id.startswith("ws-")
    assert workspace.title == "FPT workflow"
    assert workspace.status == "active"

    resumed = resume_workspace(workspace.workspace_id, root=tmp_path)
    report = get_status(workspace.workspace_id, root=tmp_path)

    assert resumed.workspace_id == workspace.workspace_id
    assert report.workspace_id == workspace.workspace_id
    assert report.title == "FPT workflow"
    assert report.mode == "research"
    assert report.status == "active"
