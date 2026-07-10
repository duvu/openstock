from __future__ import annotations

import duckdb

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import FakeLLMClient
from vnalpha.chat.context import ChatContext
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.workspace_context.integration import (
    MAX_ASSISTANT_CONTEXT_CHARS,
    MAX_ASSISTANT_CONTEXT_ITEMS,
    build_workspace_context_prompt_prefix,
)
from vnalpha.workspace_context.lifecycle import create_workspace, record_artifact
from vnalpha.workspace_context.models import WorkspaceArtifactRef
from vnalpha.workspace_context.storage import ensure_workspace_layout


def _artifact(number: int) -> WorkspaceArtifactRef:
    return WorkspaceArtifactRef(
        artifact_id=f"artifact-{number}",
        artifact_type="report",
        path=f"artifacts/report-{number}.md",
        summary=f"summary-{number}-" + "x" * 80,
        created_at="2026-07-10T00:00:00+00:00",
    )


def test_workspace_context_returns_empty_when_workspace_is_missing(tmp_path):
    # Given: an empty workspace root
    # When: assistant context is requested for an unknown workspace
    context = build_workspace_context_prompt_prefix("missing", root=tmp_path)

    # Then: no workspace data is injected
    assert context == ""


def test_workspace_context_bounds_compact_state_and_artifact_summaries(tmp_path):
    # Given: a real workspace with oversized compact text and many artifacts
    workspace = create_workspace(title="Research", root=tmp_path)
    for number in range(MAX_ASSISTANT_CONTEXT_ITEMS + 5):
        record_artifact(workspace, _artifact(number), root=tmp_path)
    paths = ensure_workspace_layout(root=tmp_path, workspace_id=workspace.workspace_id)
    paths.compact_path.write_text("compact-" + "y" * MAX_ASSISTANT_CONTEXT_CHARS)

    # When: a bounded assistant context is built
    context = build_workspace_context_prompt_prefix(
        workspace.workspace_id, root=tmp_path
    )

    # Then: the prefix and its selected artifacts stay within the published bounds
    assert len(context) <= MAX_ASSISTANT_CONTEXT_CHARS
    assert context.count("artifact-") <= MAX_ASSISTANT_CONTEXT_ITEMS
    assert "summary-0-" in context
    assert f"summary-{MAX_ASSISTANT_CONTEXT_ITEMS - 1}-" in context
    assert f"summary-{MAX_ASSISTANT_CONTEXT_ITEMS}-" not in context


def test_workspace_context_excludes_raw_events_and_states_freshness(tmp_path):
    # Given: a real workspace whose raw event log has sensitive-looking content
    workspace = create_workspace(title="Research", root=tmp_path)
    paths = ensure_workspace_layout(root=tmp_path, workspace_id=workspace.workspace_id)
    paths.events_path.write_text("RAW_EVENT_SECRET must never reach the assistant")

    # When: a bounded assistant context is built without a compact file
    context = build_workspace_context_prompt_prefix(
        workspace.workspace_id, root=tmp_path
    )

    # Then: it omits raw events and tells the assistant that live data wins
    assert "RAW_EVENT_SECRET" not in context
    assert "current warehouse and tool output is authoritative" in context.lower()
    assert "compact" not in context.lower()


def test_assistant_app_prefixes_workspace_and_existing_chat_context(tmp_path):
    # Given: a workspace prefix and an existing chat context
    workspace = create_workspace(title="Research", root=tmp_path)
    workspace_context = build_workspace_context_prompt_prefix(
        workspace.workspace_id, root=tmp_path
    )
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)
    app = AssistantApp(conn, llm_client=FakeLLMClient())

    # When: the assistant receives both optional contexts
    app.ask(
        "Show candidates",
        no_execute=True,
        chat_context=ChatContext(target_date="2026-07-10"),
        workspace_context=workspace_context,
    )

    # Then: both prefixes are retained before the original question
    prompt = conn.execute("SELECT user_prompt FROM assistant_session").fetchone()[0]
    assert prompt.startswith(workspace_context + "Context: date=2026-07-10\n")
    assert prompt.endswith("Show candidates")
    conn.close()
