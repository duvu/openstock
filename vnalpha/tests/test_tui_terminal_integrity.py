from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("textual")

from tests.tui_assertions import assert_workspace_regions


@pytest.mark.asyncio
async def test_suggestions_and_inline_logs_remain_inside_workspace() -> None:
    from vnalpha.tui.app import VnAlphaApp
    from vnalpha.tui.widgets.composer_input import ComposerInput
    from vnalpha.tui.widgets.debug_log_drawer import DebugLogDrawer

    with (
        patch.object(VnAlphaApp, "_start_workspace_lifecycle"),
        patch.object(VnAlphaApp, "_setup_router"),
        patch.object(VnAlphaApp, "_emit_tui_started"),
    ):
        app = VnAlphaApp(date="2024-01-10")
        async with app.run_test(headless=True, size=(120, 30)) as pilot:
            await pilot.pause()
            composer = pilot.app.query_one("#composer-input", ComposerInput)
            drawer = pilot.app.query_one("#debug-log-drawer", DebugLogDrawer)
            pilot.app.action_toggle_log_viewer()
            composer.set_text("/")
            await pilot.pause()

            assert composer._max_suggestions == 10
            assert drawer.display is True
            assert_workspace_regions(pilot.app)
