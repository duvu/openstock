from __future__ import annotations

from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vnalpha.workspace_context.lifecycle import (
    create_workspace,
    new_workspace,
)
from vnalpha.workspace_context.models import WorkspaceState
from vnalpha.workspace_context.storage import load_workspace_state


def _result_with_artifact():
    from vnalpha.commands.models import CommandResult, ResultArtifact

    return CommandResult(
        status="SUCCESS",
        title="/scan",
        artifacts=[ResultArtifact(name="watchlist", data={"secret": "do-not-store"})],
    )


def _router(
    workspace: WorkspaceState,
    workspace_changed: MagicMock | None = None,
):
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                target_date="2026-07-10",
                workspace=workspace,
                on_workspace_change=workspace_changed,
            )
    router._chat_controller = MagicMock()
    router._command_executor = MagicMock()
    return router, output


@pytest.mark.asyncio
async def test_tui_startup_displays_active_workspace_and_resume_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))

    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.output_stream import OutputStream
    from vnalpha.tui.widgets.status_bar import StatusBar

    with patch.object(VnAlphaApp, "_setup_router"):
        with patch.object(OutputStream, "show_assistant_message") as show_summary:
            app = VnAlphaApp(date="2026-07-10")
            async with app.run_test(headless=True) as pilot:
                workspace = app._workspace
                status_bar = pilot.app.query_one("#status-bar", StatusBar)

                assert workspace.workspace_id in app._footer_hint_text()
                assert workspace.workspace_id in status_bar._render_status()
                show_summary.assert_called_once()
                assert workspace.workspace_id in show_summary.call_args.args[0]


@pytest.mark.asyncio
async def test_router_records_sanitized_input_before_chat_routing(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    workspace = create_workspace(root=tmp_path)
    router, _ = _router(workspace)

    with patch("anyio.to_thread.run_sync", new_callable=AsyncMock) as run_sync:
        await router.route("api_key=super-secret show FPT")

    persisted = load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id)
    stored = persisted.recent_inputs[-1]
    assert stored.input_kind == "natural_language"
    assert stored.redaction_status == "redacted"
    assert stored.metadata == {"length": len("api_key=super-secret show FPT")}
    assert "super-secret" not in stored.content
    handle_turn = run_sync.call_args.args[0]
    assert isinstance(handle_turn, partial)
    assert handle_turn.func == router._chat_controller.handle_turn
    assert handle_turn.args == ("api_key=super-secret show FPT",)


@pytest.mark.asyncio
async def test_router_records_command_artifacts_without_result_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    workspace = create_workspace(root=tmp_path)
    router, _ = _router(workspace)
    result = _result_with_artifact()

    with patch("anyio.to_thread.run_sync", new_callable=AsyncMock, return_value=result):
        await router.route("/scan")

    persisted = load_workspace_state(root=tmp_path, workspace_id=workspace.workspace_id)
    artifact = persisted.active_artifacts[-1]
    assert artifact.artifact_type == "command_result"
    assert artifact.path == ""
    assert artifact.summary == "Command artifact: watchlist"
    assert artifact.metadata == {"name": "watchlist"}


@pytest.mark.asyncio
async def test_context_command_switch_notifies_tui_of_latest_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    workspace = create_workspace(root=tmp_path)
    workspace_changed = MagicMock()
    router, _ = _router(workspace, workspace_changed)
    result = _result_with_artifact()

    async def execute_and_switch(*_args):
        new_workspace(root=tmp_path)
        return result

    with patch("anyio.to_thread.run_sync", new_callable=AsyncMock) as run_sync:
        run_sync.side_effect = execute_and_switch
        await router.route("/context new")

    switched = load_workspace_state(
        root=tmp_path,
        workspace_id=router._workspace.workspace_id,
    )
    assert switched.workspace_id != workspace.workspace_id
    workspace_changed.assert_called_once_with(switched)


@pytest.mark.asyncio
async def test_router_passes_raw_chat_and_bounded_workspace_context_separately(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    workspace = create_workspace(root=tmp_path)
    router, _ = _router(workspace)

    with patch("anyio.to_thread.run_sync", new_callable=AsyncMock) as run_sync:
        await router.route("Show FPT candidates")

    handle_turn = run_sync.call_args.args[0]
    assert isinstance(handle_turn, partial)
    assert handle_turn.args == ("Show FPT candidates",)
    workspace_context = handle_turn.keywords["workspace_context"]
    assert workspace_context.startswith("# Workspace Context")
    assert (
        "current warehouse and tool output is authoritative"
        in workspace_context.lower()
    )
