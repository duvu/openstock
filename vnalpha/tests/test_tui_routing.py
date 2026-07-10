from __future__ import annotations

from pathlib import Path
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
