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


# ---------------------------------------------------------------------------
# TUI binding and screen tests
# ---------------------------------------------------------------------------


class TestTuiAskBinding:
    def test_tui_app_has_ask_binding(self):
        """VnAlphaApp BINDINGS must include the 'a' key."""
        try:
            from vnalpha.tui.app import VnAlphaApp
        except ImportError:
            pytest.skip("textual not installed")
        keys = [b.key for b in VnAlphaApp.BINDINGS]
        assert "a" in keys

    def test_tui_app_ask_binding_label(self):
        """The 'a' binding must have label 'Ask'."""
        try:
            from vnalpha.tui.app import VnAlphaApp
        except ImportError:
            pytest.skip("textual not installed")
        binding = next((b for b in VnAlphaApp.BINDINGS if b.key == "a"), None)
        assert binding is not None
        assert binding.description == "Ask"

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
