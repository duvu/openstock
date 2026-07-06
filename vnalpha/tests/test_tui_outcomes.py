"""TUI smoke tests for the Outcome Review screen."""

import pytest

try:
    import textual
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


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
            assert term not in src.lower(), f"Forbidden term '{term}' found in outcomes screen"

    @pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
    def test_outcome_screen_bindings(self):
        from vnalpha.tui.screens.outcomes import OutcomeScreen
        screen = OutcomeScreen()
        bindings = [b.key for b in screen.BINDINGS]
        assert "escape" in bindings

    @pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
    def test_tui_app_has_outcomes_binding(self):
        from vnalpha.tui.app import VnAlphaApp
        bindings = [b.key for b in VnAlphaApp.BINDINGS]
        assert "o" in bindings
