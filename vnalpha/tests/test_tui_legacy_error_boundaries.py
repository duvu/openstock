from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rich.text import Text


def _assert_generic_literal(status: MagicMock, subject: str) -> None:
    value = status.update.call_args.args[0]
    assert isinstance(value, Text)
    assert value.plain == f"{subject} is unavailable. Check logs and retry."
    assert "raw-secret" not in value.plain


def test_watchlist_failure_closes_connection_and_renders_literal_error() -> None:
    from vnalpha.tui.screens.watchlist import WatchlistScreen

    screen = WatchlistScreen(target_date="2026-07-17")
    status = MagicMock()
    connection = MagicMock()

    with (
        patch.object(screen, "query_one", return_value=status),
        patch("vnalpha.warehouse.connection.get_connection", return_value=connection),
        patch(
            "vnalpha.warehouse.repositories.get_watchlist",
            side_effect=RuntimeError("api_key=raw-secret"),
        ),
        patch("vnalpha.tui.screens.watchlist.capture_tui_exception") as capture,
    ):
        screen._load_data()

    connection.close.assert_called_once_with()
    capture.assert_called_once()
    _assert_generic_literal(status, "Watchlist")


def test_rejected_failure_closes_connection_and_renders_literal_error() -> None:
    from vnalpha.tui.screens.rejected import RejectedScreen

    screen = RejectedScreen(target_date="2026-07-17")
    status = MagicMock()
    connection = MagicMock()
    connection.execute.side_effect = RuntimeError("token=raw-secret")

    with (
        patch.object(screen, "query_one", return_value=status),
        patch("vnalpha.warehouse.connection.get_connection", return_value=connection),
        patch("vnalpha.tui.screens.rejected.capture_tui_exception") as capture,
    ):
        screen._load_data()

    connection.close.assert_called_once_with()
    capture.assert_called_once()
    _assert_generic_literal(status, "Rejected-symbol data")


def test_detail_failure_closes_connection_and_renders_literal_error() -> None:
    from vnalpha.tui.screens.detail import DetailScreen

    screen = DetailScreen("VCB", target_date="2026-07-17")
    status = MagicMock()
    connection = MagicMock()

    with (
        patch.object(screen, "query_one", return_value=status),
        patch("vnalpha.warehouse.connection.get_connection", return_value=connection),
        patch(
            "vnalpha.warehouse.repositories.get_candidate_score",
            side_effect=RuntimeError("password=raw-secret"),
        ),
        patch("vnalpha.tui.screens.detail.capture_tui_exception") as capture,
    ):
        screen._load_detail()

    connection.close.assert_called_once_with()
    capture.assert_called_once()
    _assert_generic_literal(status, "Symbol detail")


def test_quality_failure_closes_client_and_renders_literal_error() -> None:
    from vnalpha.tui.screens.quality import QualityScreen

    screen = QualityScreen()
    status = MagicMock()
    client = MagicMock()
    client.get_provider_health.side_effect = RuntimeError("secret=raw-secret")
    config = SimpleNamespace(vnstock=SimpleNamespace(base_url="http://localhost"))

    with (
        patch.object(screen, "query_one", return_value=status),
        patch("vnalpha.core.config.get_config", return_value=config),
        patch("vnalpha.clients.vnstock.client.VnstockClient", return_value=client),
        patch("vnalpha.tui.screens.quality.capture_tui_exception") as capture,
    ):
        screen._load_data()

    client.close.assert_called_once_with()
    capture.assert_called_once()
    _assert_generic_literal(status, "Provider health")


def test_home_failure_is_captured_and_renders_literal_error() -> None:
    from vnalpha.tui.screens.home import HomeScreen

    screen = HomeScreen()
    status = MagicMock()

    with (
        patch.object(screen, "query_one", return_value=status),
        patch(
            "vnalpha.core.config.get_config",
            side_effect=RuntimeError("credential=raw-secret"),
        ),
        patch("vnalpha.tui.screens.home.capture_tui_exception") as capture,
    ):
        screen._load_status()

    capture.assert_called_once()
    _assert_generic_literal(status, "System status")
