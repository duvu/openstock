"""TUI smoke tests for the Outcome Review screen."""

import importlib.util
from unittest.mock import Mock

import pytest

HAS_TEXTUAL = importlib.util.find_spec("textual") is not None


class TestOutcomeScreenImport:
    def test_outcome_screen_importable(self):
        from vnalpha.tui.screens.outcomes import OutcomeScreen

        assert OutcomeScreen is not None

    def test_outcome_screen_has_target_date(self):
        from vnalpha.tui.screens.outcomes import OutcomeScreen

        screen = OutcomeScreen(target_date="2026-07-01", horizon=20)
        assert screen.target_date == "2026-07-01"
        assert screen.horizon == 20

    def test_outcome_screen_no_trading_language(self):
        import inspect

        from vnalpha.tui.screens import outcomes

        src = inspect.getsource(outcomes)
        for term in ["buy signal", "sell signal", "place order", "portfolio action"]:
            assert term not in src.lower(), (
                f"Forbidden term '{term}' found in outcomes screen"
            )

    @pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
    def test_outcome_screen_bindings(self):
        from vnalpha.tui.screens.outcomes import OutcomeScreen

        screen = OutcomeScreen()
        bindings = [b.key for b in screen.BINDINGS]
        assert "escape" in bindings

    @pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
    def test_tui_app_has_composer_input(self):
        import inspect

        from vnalpha.tui.app import VnAlphaApp

        src = inspect.getsource(VnAlphaApp.compose)
        assert "ComposerInput" in src

    @pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
    def test_outcome_screen_closes_connection_if_migration_fails(self, monkeypatch):
        import vnalpha.warehouse.connection as connection
        import vnalpha.warehouse.migrations as migrations
        from vnalpha.tui.screens.outcomes import OutcomeScreen

        fake_connection = Mock()

        def get_connection():
            return fake_connection

        def fail_migrations(*, conn=None) -> None:
            raise RuntimeError("schema migration failed")

        monkeypatch.setattr(connection, "get_connection", get_connection)
        monkeypatch.setattr(migrations, "run_migrations", fail_migrations)

        screen = OutcomeScreen()
        assert screen._open_connection() is None
        fake_connection.close.assert_called_once()
