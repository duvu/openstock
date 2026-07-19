"""CLI and TUI contract tests for Phase 5.9 'vnalpha ask' command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vnalpha.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_answer():
    from vnalpha.assistant.models import AssistantAnswer, AssistantPlan

    answer = AssistantAnswer(
        summary="3 strong candidates identified.",
        basis="Based on persisted candidate_score.",
        risks_caveats="Check THIN_VOLUME flag.",
        tool_trace_summary="Called watchlist.scan.",
    )
    plan = AssistantPlan(intent="scan_candidates", steps=[])
    return answer, plan


def _make_refusal():
    from vnalpha.assistant.models import AssistantPlan, RefusalMessage

    refusal = RefusalMessage(
        reason="Trading execution is not allowed.",
        policy_category="TRADING_EXECUTION",
        suggestion="Ask about a symbol's score instead.",
    )
    plan = AssistantPlan(
        intent="unsupported_or_unsafe",
        steps=[],
        refusal_reason="Trading execution is not allowed.",
    )
    return refusal, plan


def mock_ask_success(question, *, date=None, no_execute=False):
    return _make_answer()


def mock_ask_refusal(question, *, date=None, no_execute=False):
    return _make_refusal()


# ---------------------------------------------------------------------------
# Help / flag presence tests
# ---------------------------------------------------------------------------


class TestAskHelp:
    def test_ask_help_shows_ask_command(self):
        """'vnalpha --help' output must contain 'ask'."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ask" in result.output

    def test_ask_help_flags(self):
        """'vnalpha ask --help' must list all four flags."""
        result = runner.invoke(app, ["ask", "--help"])
        assert result.exit_code == 0
        assert "--show-plan" in result.output
        assert "--trace" in result.output
        assert "--no-execute" in result.output
        assert "--date" in result.output

    def test_ask_command_exists(self):
        """Invoking 'ask' without arguments should not produce 'No such command'."""
        result = runner.invoke(app, ["ask", "--help"])
        assert "No such command" not in result.output

    def test_ask_show_plan_flag_in_help(self):
        result = runner.invoke(app, ["ask", "--help"])
        assert "--show-plan" in result.output

    def test_ask_trace_flag_in_help(self):
        result = runner.invoke(app, ["ask", "--help"])
        assert "--trace" in result.output

    def test_ask_no_execute_flag_in_help(self):
        result = runner.invoke(app, ["ask", "--help"])
        assert "--no-execute" in result.output

    def test_ask_date_flag_in_help(self):
        result = runner.invoke(app, ["ask", "--help"])
        assert "--date" in result.output


# ---------------------------------------------------------------------------
# Functional tests (with mocked AssistantApp.ask)
# ---------------------------------------------------------------------------


class TestAskFunctional:
    @pytest.fixture(autouse=True)
    def _configure_mock_llm_gateway(self, monkeypatch):
        monkeypatch.setenv(
            "VNALPHA_LLM_ENDPOINT",
            "https://gateway.example.test/v1/chat/completions",
        )
        monkeypatch.setenv("VNALPHA_LLM_MODEL", "verified-test-model")
        monkeypatch.setenv("VNALPHA_LLM_API_KEY", "dedicated-test-key")

    def test_ask_output_is_research_language(self):
        """Answer output must not contain buy/sell/order language."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_success
        ):
            result = runner.invoke(app, ["ask", "Show strongest VN30 candidates today"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "buy" not in output_lower
        assert "sell" not in output_lower
        assert "order" not in output_lower

    def test_ask_output_contains_summary(self):
        """Answer panel must contain the summary text from the mocked answer."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_success
        ):
            result = runner.invoke(app, ["ask", "Show strongest VN30 candidates today"])
        assert result.exit_code == 0
        assert "3 strong candidates identified" in result.output

    def test_ask_refusal_exits_nonzero(self):
        """A RefusalMessage result must produce exit code 1."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_refusal
        ):
            result = runner.invoke(app, ["ask", "Buy FPT for me"])
        assert result.exit_code == 1

    def test_ask_refusal_shows_refused_panel(self):
        """A RefusalMessage result must render the refusal reason in output."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_refusal
        ):
            result = runner.invoke(app, ["ask", "Buy FPT for me"])
        assert "Trading execution" in result.output or "Refused" in result.output

    def test_ask_show_plan_flag_renders_plan(self):
        """--show-plan must add 'Research Plan' panel to output."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_success
        ):
            result = runner.invoke(app, ["ask", "Show watchlist", "--show-plan"])
        assert result.exit_code == 0
        assert "Research Plan" in result.output or "Plan for intent" in result.output

    def test_ask_trace_flag_renders_trace(self):
        """--trace must add trace summary to output."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_success
        ):
            result = runner.invoke(app, ["ask", "Show watchlist", "--trace"])
        assert result.exit_code == 0
        assert "Tool Trace" in result.output or "watchlist.scan" in result.output

    def test_ask_no_execute_flag_renders_plan(self):
        """--no-execute must show the plan panel."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_success
        ):
            result = runner.invoke(app, ["ask", "Show watchlist", "--no-execute"])
        assert result.exit_code == 0
        assert "Research Plan" in result.output or "Plan for intent" in result.output

    def test_ask_basis_shown_in_answer(self):
        """Answer panel must include basis field content."""
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask", side_effect=mock_ask_success
        ):
            result = runner.invoke(app, ["ask", "Why is FPT in the watchlist?"])
        assert result.exit_code == 0
        assert "persisted candidate_score" in result.output

    def test_ask_assistant_error_renders_without_console_type_error(self):
        """Assistant errors must render cleanly and exit non-zero."""
        from vnalpha.assistant.errors import AssistantError

        with patch(
            "vnalpha.assistant.app.AssistantApp.ask",
            side_effect=AssistantError("LLM unavailable"),
        ):
            result = runner.invoke(app, ["ask", "Show watchlist"])
        assert result.exit_code == 1
        assert "Assistant error" in result.output
        assert "unexpected keyword argument 'err'" not in result.output

    def test_ask_without_date_uses_current_market_session(self, monkeypatch) -> None:
        # Given: the current calendar day resolves to the previous market session.
        import duckdb

        from vnalpha.cli_app import ask as ask_module

        connection = duckdb.connect()
        observed_dates: list[str | None] = []
        monkeypatch.setattr(
            "vnalpha.warehouse.connection.get_connection", lambda: connection
        )
        monkeypatch.setattr(
            ask_module,
            "resolve_market_session_date",
            lambda _value: "2026-07-17",
            raising=False,
        )

        def record_date(question, *, date=None, no_execute=False):
            del question, no_execute
            observed_dates.append(date)
            return _make_answer()

        # When: `vnalpha ask` runs without an explicit --date.
        try:
            with patch(
                "vnalpha.assistant.app.AssistantApp.ask", side_effect=record_date
            ):
                result = runner.invoke(app, ["ask", "Phân tích sâu mã VCB"])
        finally:
            connection.close()

        # Then: the assistant receives the resolved market session once.
        assert result.exit_code == 0
        assert observed_dates == ["2026-07-17"]


# ---------------------------------------------------------------------------
# TUI binding and screen tests
# ---------------------------------------------------------------------------


class TestTuiAskBinding:
    def test_tui_app_uses_composer_input(self):
        """VnAlphaApp uses ComposerInput in new workspace design."""
        try:
            from vnalpha.tui.app import VnAlphaApp
        except ImportError:
            pytest.skip("textual not installed")
        import inspect

        src = inspect.getsource(VnAlphaApp.compose)
        assert "ComposerInput" in src

    def test_tui_app_ask_via_chat_controller(self):
        """Ask functionality routed via ChatController through TuiInputRouter."""
        try:
            from vnalpha.tui.input_router import TuiInputRouter
        except ImportError:
            pytest.skip("textual not installed")
        assert hasattr(TuiInputRouter, "_route_chat")

    def test_tui_default_target_uses_current_market_session(self, monkeypatch) -> None:
        # Given: the current calendar day resolves to the previous market session.
        from vnalpha.tui import app as tui_app_module

        monkeypatch.setattr(
            tui_app_module,
            "resolve_market_session_date",
            lambda _value: "2026-07-17",
            raising=False,
        )

        # When: the TUI is created without --date.
        tui_app = tui_app_module.VnAlphaApp()

        # Then: its shared command/chat target is the market session.
        assert tui_app.target_date == "2026-07-17"

    def test_assistant_screen_importable(self):
        """AssistantScreen must be importable (skip if textual not installed)."""
        try:
            import textual  # noqa: F401
        except ImportError:
            pytest.skip("textual not installed")
        from vnalpha.tui.screens.assistant import AssistantScreen

        assert AssistantScreen is not None

    def test_assistant_screen_has_escape_binding(self):
        """AssistantScreen must have escape → pop_screen binding."""
        try:
            import textual  # noqa: F401

            from vnalpha.tui.screens.assistant import AssistantScreen
        except ImportError:
            pytest.skip("textual not installed")
        bindings = AssistantScreen.BINDINGS
        keys = [b[0] if isinstance(b, tuple) else b.key for b in bindings]
        assert "escape" in keys


# ---------------------------------------------------------------------------
# Documentation existence test
# ---------------------------------------------------------------------------


class TestAssistantDocs:
    def test_assistant_docs_exists(self):
        """docs/ASSISTANT.md must exist."""
        docs_path = Path(__file__).parent.parent / "docs" / "ASSISTANT.md"
        assert docs_path.exists(), f"Expected docs/ASSISTANT.md at {docs_path}"

    def test_assistant_docs_has_content(self):
        """docs/ASSISTANT.md must be non-empty and contain Phase 5.9 reference."""
        docs_path = Path(__file__).parent.parent / "docs" / "ASSISTANT.md"
        if not docs_path.exists():
            pytest.skip("docs/ASSISTANT.md not found")
        content = docs_path.read_text()
        assert len(content) > 100
        assert "5.9" in content
