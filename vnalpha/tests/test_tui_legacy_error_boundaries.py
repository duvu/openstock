from __future__ import annotations

from unittest.mock import MagicMock, patch

from rich.text import Text

from vnalpha.tui.screens.watchlist import WatchlistScreen


def _assert_generic_literal(status: MagicMock, subject: str) -> None:
    value = status.update.call_args.args[0]
    assert isinstance(value, Text)
    assert value.plain == f"{subject} is unavailable. Check logs and retry."
    assert "raw-secret" not in value.plain


def test_watchlist_failure_closes_connection_and_renders_literal_error() -> None:
    screen = WatchlistScreen(target_date="2026-07-17")
    status = MagicMock()
    connection = MagicMock()

    with (
        patch.object(screen, "query_one", return_value=status),
        patch("vnalpha.tui.screens.watchlist.get_connection", return_value=connection),
        patch(
            "vnalpha.tui.screens.watchlist.get_watchlist",
            side_effect=RuntimeError("api_key=raw-secret"),
        ),
        patch("vnalpha.tui.screens.watchlist.capture_tui_exception") as capture,
    ):
        screen._load_data()

    connection.close.assert_called_once_with()
    capture.assert_called_once()
    _assert_generic_literal(status, "Watchlist")
