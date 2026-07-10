from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_context_command_output_rendered_into_stream():
    from vnalpha.commands.models import CommandResult, ResultPanel
    from vnalpha.tui.widgets.output_stream import OutputStream

    output = MagicMock(spec=OutputStream)
    with patch("vnalpha.tui.input_router.TuiInputRouter._setup_controller"):
        with patch("vnalpha.tui.input_router.TuiInputRouter._setup_executor"):
            from vnalpha.tui.input_router import TuiInputRouter

            router = TuiInputRouter(output_stream=output, target_date=None)

    router._command_executor = MagicMock()
    router._chat_controller = MagicMock()

    command_result = CommandResult(
        status="SUCCESS",
        title="/context status",
        summary="Workspace is active.",
        panels=[
            ResultPanel(
                title="Workspace Health",
                content={"status": "active", "workspace_id": "ws-1"},
            )
        ],
    )

    with patch(
        "vnalpha.tui.routing.command_path.anyio.to_thread.run_sync",
        new_callable=AsyncMock,
    ) as mock_thread:
        mock_thread.return_value = command_result
        with patch(
            "vnalpha.tui.routing.command_path.CommandPath.result_to_markup",
            return_value="[green]/context status[/green]",
        ):
            await router.route("/context status")

    output.show_command_result.assert_called_once_with(
        "/context status", "[green]/context status[/green]"
    )
