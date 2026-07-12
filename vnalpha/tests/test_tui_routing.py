from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vnalpha.workspace_context.lifecycle import create_workspace


def test_compatibility_import_reexports_routing_router() -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.routing.router import TuiInputRouter as RoutingTuiInputRouter

    assert TuiInputRouter is RoutingTuiInputRouter


@pytest.mark.asyncio
async def test_router_delegates_command_and_chat_to_focused_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                workspace=create_workspace(root=tmp_path),
            )
    command_path = AsyncMock()
    chat_path = AsyncMock()
    router._command_path = command_path
    router._chat_path = chat_path

    await router.route("/scan FPT")
    await router.route("Show FPT candidates")

    command_path.route.assert_awaited_once_with(router, "/scan FPT")
    chat_path.route.assert_awaited_once_with(router, "Show FPT candidates")


@pytest.mark.asyncio
async def test_busy_submission_is_rejected_before_workspace_persistence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                workspace=create_workspace(root=tmp_path),
            )
    router._busy = True
    router._record_workspace_input = MagicMock()

    await router.route("show FPT")

    router._record_workspace_input.assert_not_called()
    output.show_warning.assert_called_once()


@pytest.mark.asyncio
async def test_router_shows_user_input_only_for_natural_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                workspace=create_workspace(root=tmp_path),
            )

    command_path = AsyncMock()
    chat_path = AsyncMock()
    router._command_path = command_path
    router._chat_path = chat_path

    await router.route("/scan")
    await router.route("compare FPT")

    command_path.route.assert_awaited_once_with(router, "/scan")
    chat_path.route.assert_awaited_once_with(router, "compare FPT")
    output.show_user_input.assert_called_once_with("compare FPT")


@pytest.mark.asyncio
async def test_workspace_input_failure_does_not_block_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.commands.models import CommandResult
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                workspace=create_workspace(root=tmp_path),
            )
    router._command_executor = MagicMock()
    router._command_executor.execute.return_value = CommandResult(
        status="SUCCESS", title="scan", summary="completed"
    )
    monkeypatch.setattr(
        "vnalpha.tui.workspace_context.record_workspace_input",
        MagicMock(side_effect=RuntimeError("workspace unavailable")),
    )

    await router.route("/scan")

    router._command_executor.execute.assert_called_once_with("/scan")
    output.show_command_result.assert_called_once()


@pytest.mark.asyncio
async def test_router_scopes_session_aware_commands_to_chat_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from vnalpha.commands.models import CommandResult
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    class SessionAwareExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None]] = []

        def execute(self, raw: str, *, session_scope_id: str | None = None):
            self.calls.append((raw, session_scope_id))
            return CommandResult(status="SUCCESS", title="scan", summary="ok")

    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))
    output = MagicMock(spec=OutputStream)
    with patch.object(TuiInputRouter, "_setup_controller"):
        with patch.object(TuiInputRouter, "_setup_executor"):
            router = TuiInputRouter(
                output_stream=output,
                workspace=create_workspace(root=tmp_path),
            )
    executor = SessionAwareExecutor()
    router._command_executor = executor
    router._chat_controller = SimpleNamespace(_chat_session_id="chat-session-a")

    await router.route("/scan")

    assert executor.calls == [("/scan", "chat-session-a")]
