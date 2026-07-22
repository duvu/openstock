from __future__ import annotations

import json

from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.workspace_context.compaction import compact_workspace
from vnalpha.workspace_context.lifecycle import create_workspace


def test_compaction_can_use_routed_long_context_client(tmp_path) -> None:
    workspace = create_workspace(root=tmp_path)
    client = FakeLLMClient(
        responses=[
            (
                "# Compact Workspace Summary\n\n- Routed summary",
                {"route_profile": "long_context"},
            )
        ]
    )

    result = compact_workspace(
        workspace.workspace_id,
        root=tmp_path,
        llm_client=client,
    )

    compact_text = (tmp_path / workspace.workspace_id / "compact.md").read_text(
        encoding="utf-8"
    )
    assert "Routed summary" in compact_text
    assert result.warnings == []
    assert client.call_metadata[0]["stage"] == "compact"
    assert client.call_metadata[0]["task_type"] == "workspace_compaction"
    event = json.loads(
        (tmp_path / workspace.workspace_id / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[-1]
    )
    assert event["metadata"]["model_route"] == {"profile": "long_context"}
