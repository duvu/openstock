from __future__ import annotations

import json

from vnalpha.workspace_context.lifecycle import (
    create_workspace,
    record_input,
)
from vnalpha.workspace_context.storage import (
    load_workspace_state,
)


def test_input_retention_archives_entries_outside_configured_bound(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_MAX_INPUTS", "2")
    workspace = create_workspace(root=tmp_path)

    for index in range(3):
        record_input(workspace, f"input-{index}", "user", root=tmp_path)

    state = load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id)
    archive_path = tmp_path / workspace.workspace_id / "archive" / "inputs.jsonl"
    archived = [json.loads(line) for line in archive_path.read_text().splitlines()]

    assert [item.summary for item in state.recent_inputs] == ["input-1", "input-2"]
    assert len(archived) == 1
    assert archived[0]["summary"] == "input-0"
