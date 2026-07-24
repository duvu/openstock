from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vnalpha.commands.models import CommandResult, ResultArtifact
from vnalpha.tui import research_date
from vnalpha.tui.app import VnAlphaApp
from vnalpha.tui.input_router import TuiInputRouter
from vnalpha.tui.widgets.output_stream import OutputStream
from vnalpha.tui.widgets.status_bar import StatusBar
from vnalpha.warehouse.connection import WarehouseOpenError, WarehouseOpenFailureKind
from vnalpha.workspace_context.models import WorkspaceState


def _result_with_artifact():
    return CommandResult(
        status="SUCCESS",
        title="/scan",
        artifacts=[ResultArtifact(name="watchlist", data={"secret": "do-not-store"})],
    )


def _router(
    workspace: WorkspaceState,
    workspace_changed: MagicMock | None = None,
):
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

    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(research_date, "get_connection", lambda: connection)

    def resolve_implicit_date(value, *, conn=None) -> str:
        assert value is None
        assert conn is connection
        return "2026-07-23"

    monkeypatch.setattr(research_date, "resolve_date", resolve_implicit_date)
    assert research_date.resolve_tui_research_date(None) == "2026-07-23"

    def unavailable_connection() -> object:
        raise WarehouseOpenError(
            WarehouseOpenFailureKind.UNAVAILABLE,
            "warehouse is unavailable",
        )

    monkeypatch.setattr(research_date, "get_connection", unavailable_connection)

    def resolve_calendar_date(value, *, conn=None) -> str:
        assert value is None
        assert conn is None
        return "2026-07-24"

    monkeypatch.setattr(research_date, "resolve_date", resolve_calendar_date)
    assert research_date.resolve_tui_research_date(None) == "2026-07-24"
