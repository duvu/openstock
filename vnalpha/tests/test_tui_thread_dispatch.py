from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import anyio
import pytest

from vnalpha.workspace_context.lifecycle import create_workspace


@pytest.fixture(autouse=True)
def workspace_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VNALPHA_WORKSPACE_ROOT", str(tmp_path))


@pytest.mark.asyncio
async def test_controller_callbacks_use_app_call_from_thread(tmp_path: Path) -> None:
    from vnalpha.tui.input_router import TuiInputRouter
    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    app_call_from_thread = MagicMock()
    controller = MagicMock()
    with patch.object(TuiInputRouter, "_bootstrap_session", return_value=None):
        with patch(
            "vnalpha.chat.controller.ChatController", return_value=controller
        ) as chat_controller:
            with patch.object(TuiInputRouter, "_setup_executor"):
                TuiInputRouter(
                    output_stream=output,
                    workspace=create_workspace(root=tmp_path),
                    ui_dispatcher=app_call_from_thread,
                )

    on_message = chat_controller.call_args.kwargs["on_message"]
    on_trace = chat_controller.call_args.kwargs["on_trace"]
    trace_event = MagicMock(status="RUNNING", tool_name="watchlist.scan")

    await anyio.to_thread.run_sync(on_message, "assistant", "thread-safe message")
    await anyio.to_thread.run_sync(on_trace, trace_event)

    assert app_call_from_thread.call_count == 2
    output.show_assistant_message.assert_not_called()
    output.show_trace_event.assert_not_called()
