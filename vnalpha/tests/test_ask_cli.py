"""CLI and TUI contract tests for Phase 5.9 'vnalpha ask' command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vnalpha.cli import app

runner = CliRunner()


def _force_terminal_console(monkeypatch) -> None:
    from rich.console import Console

    class ForcedTerminalConsole(Console):
        def __init__(self, *args, **kwargs):
            super().__init__(
                *args,
                **kwargs,
                force_terminal=True,
                color_system="standard",
            )

    monkeypatch.setattr("rich.console.Console", ForcedTerminalConsole)


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


def mock_ask_success(question, *, date=None, date_is_implicit=None, no_execute=False):
    return _make_answer()


def mock_ask_refusal(question, *, date=None, date_is_implicit=None, no_execute=False):
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
        assert "Assistant request failed. Check logs and retry." in result.output
        assert "unexpected keyword argument 'err'" not in result.output

    def test_ask_without_date_uses_current_market_session(self, monkeypatch) -> None:
        # Given: the current calendar day resolves to the previous market session.
        import duckdb

        from vnalpha.cli_app import ask as ask_module
        from vnalpha.warehouse.migrations import run_migrations

        connection = duckdb.connect()
        run_migrations(conn=connection)
        connection.execute(
            "INSERT INTO daily_watchlist (date, rank, symbol) VALUES (?, 1, 'VCB')",
            ["2026-07-15"],
        )
        observed_dates: list[tuple[str | None, bool | None]] = []
        monkeypatch.setattr(
            "vnalpha.warehouse.connection.get_connection", lambda: connection
        )
        monkeypatch.setattr(
            ask_module, "resolve_date", lambda _value, conn: "2026-07-15"
        )

        def record_date(
            question, *, date=None, date_is_implicit=None, no_execute=False
        ):
            del question, no_execute
            observed_dates.append((date, date_is_implicit))
            return _make_answer()

        # When: `vnalpha ask` runs without an explicit --date.
        try:
            with patch(
                "vnalpha.assistant.app.AssistantApp.ask", side_effect=record_date
            ):
                result = runner.invoke(app, ["ask", "Phân tích sâu mã VCB"])
        finally:
            connection.close()

        # Then: CLI preserves its generic date and marks the implicit provenance.
        assert result.exit_code == 0
        assert observed_dates == [("2026-07-15", True)]

    def test_ask_calendar_coverage_failure_is_user_facing_and_redacted(
        self, monkeypatch
    ) -> None:
        import duckdb

        from vnalpha.assistant.errors import AssistantInputValidationError
        from vnalpha.warehouse.migrations import run_migrations

        connection = duckdb.connect()
        run_migrations(conn=connection)
        monkeypatch.setattr(
            "vnalpha.warehouse.connection.get_connection", lambda: connection
        )
        _force_terminal_console(monkeypatch)

        private_fragment = "CLASSIFIED_SECRET_91ef"
        try:
            with patch(
                "vnalpha.assistant.app.AssistantApp.ask",
                side_effect=AssistantInputValidationError(
                    "calendar [link=https://example.invalid]coverage[/link] unavailable "
                    f"authorization=Bearer {private_fragment}"
                ),
            ):
                result = runner.invoke(app, ["ask", "Phân tích sâu mã VCB"])
        finally:
            connection.close()

        assert result.exit_code == 1
        assert "[link=https://example.invalid]coverage[/link]" in result.output
        assert private_fragment not in result.output
        assert "[REDACTED]" in result.output
        assert "Unexpected error" not in result.output
        assert "\x1b]8;" not in result.output

    def test_ask_malformed_date_is_user_facing(self, monkeypatch) -> None:
        import duckdb

        from vnalpha.warehouse.migrations import run_migrations

        connection = duckdb.connect()
        run_migrations(conn=connection)
        monkeypatch.setattr(
            "vnalpha.warehouse.connection.get_connection", lambda: connection
        )

        _force_terminal_console(monkeypatch)
        try:
            result = runner.invoke(
                app,
                [
                    "ask",
                    "Phân tích sâu mã VCB",
                    "--date",
                    "[link=https://example.invalid]bad[/link]",
                ],
                color=True,
            )
        finally:
            connection.close()

        assert result.exit_code == 1
        assert "Assistant error:" in result.output
        assert "Unexpected error" not in result.output
        assert "\x1b]8;" not in result.output

    def test_ask_malformed_date_redacts_credentials(self, monkeypatch) -> None:
        import duckdb

        from vnalpha.warehouse.migrations import run_migrations

        connection = duckdb.connect()
        run_migrations(conn=connection)
        monkeypatch.setattr(
            "vnalpha.warehouse.connection.get_connection", lambda: connection
        )
        private_fragment = "DATE_SECRET_7d9a"

        try:
            result = runner.invoke(
                app,
                [
                    "ask",
                    "Phân tích sâu mã VCB",
                    "--date",
                    f"2026-07-19 password={private_fragment}",
                ],
            )
        finally:
            connection.close()

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "[REDACTED]" in result.output

    def test_ask_unexpected_assistant_error_is_generic(self, monkeypatch) -> None:
        from vnalpha.assistant.errors import AssistantError

        private_fragment = "PROVIDER_SECRET_42"
        with patch(
            "vnalpha.assistant.app.AssistantApp.ask",
            side_effect=AssistantError(f"provider password={private_fragment}"),
        ):
            result = runner.invoke(app, ["ask", "Show watchlist"])

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "Assistant request failed. Check logs and retry." in result.output

    def test_ask_llm_config_error_is_generic(self) -> None:
        from vnalpha.assistant.errors import LLMConfigError

        private_fragment = "CONFIG_SECRET_84"
        with patch(
            "vnalpha.assistant.gateway.LLMGatewayConfig.from_env",
            side_effect=LLMConfigError(f"api_key={private_fragment}"),
        ):
            result = runner.invoke(app, ["ask", "Show watchlist"])

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "LLM route is not configured" in result.output
        assert "correctly" in result.output

    def test_ask_warehouse_initialization_error_is_generic(self) -> None:
        private_fragment = "WAREHOUSE_SECRET_57"
        with patch(
            "vnalpha.warehouse.connection.get_connection",
            side_effect=RuntimeError(f"path password={private_fragment}"),
        ):
            result = runner.invoke(app, ["ask", "Show watchlist"])

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "Traceback" not in result.output
        assert "Assistant request failed. Check logs and retry." in result.output

    def test_ask_migration_error_is_generic_and_closes_connection(self) -> None:
        from unittest.mock import MagicMock

        connection = MagicMock()
        private_fragment = "MIGRATION_SECRET_32"
        with (
            patch(
                "vnalpha.warehouse.connection.get_connection",
                return_value=connection,
            ),
            patch(
                "vnalpha.warehouse.migrations.run_migrations",
                side_effect=RuntimeError(f"password={private_fragment}"),
            ),
        ):
            result = runner.invoke(app, ["ask", "Show watchlist"])

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "Traceback" not in result.output
        assert "Assistant request failed. Check logs and retry." in result.output
        connection.close.assert_called_once_with()

    def test_ask_date_resolution_runtime_error_is_generic_and_closes(self) -> None:
        from unittest.mock import MagicMock

        connection = MagicMock()
        private_fragment = "DATE_RESOLVE_SECRET_52"
        connection.execute.side_effect = RuntimeError(
            f"warehouse path password={private_fragment}"
        )
        with (
            patch(
                "vnalpha.warehouse.connection.get_connection",
                return_value=connection,
            ),
            patch("vnalpha.warehouse.migrations.run_migrations"),
        ):
            result = runner.invoke(app, ["ask", "Show watchlist"])

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "Traceback" not in result.output
        assert "Assistant request failed. Check logs and retry." in result.output
        connection.close.assert_called_once_with()

    def test_ask_close_error_is_generic_and_returns_failure(self) -> None:
        from unittest.mock import MagicMock

        connection = MagicMock()
        private_fragment = "CLOSE_SECRET_28"
        connection.close.side_effect = RuntimeError(
            f"warehouse path password={private_fragment}"
        )
        with (
            patch(
                "vnalpha.warehouse.connection.get_connection",
                return_value=connection,
            ),
            patch("vnalpha.warehouse.migrations.run_migrations"),
            patch(
                "vnalpha.assistant.app.AssistantApp.ask",
                side_effect=mock_ask_success,
            ),
        ):
            result = runner.invoke(
                app,
                ["ask", "Show watchlist", "--date", "2026-07-17"],
            )

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "Traceback" not in result.output
        assert "Assistant request failed. Check logs and retry." in result.output
        connection.close.assert_called_once_with()

    def test_ask_invalid_explicit_date_fails_before_warehouse_open(self) -> None:
        with patch("vnalpha.warehouse.connection.get_connection") as get_connection:
            result = runner.invoke(
                app,
                ["ask", "Phân tích sâu mã VCB", "--date", "not-a-date"],
            )

        assert result.exit_code == 1
        get_connection.assert_not_called()

    def test_ask_sanitizes_successful_dynamic_output(self, monkeypatch) -> None:
        from vnalpha.assistant.models import (
            AssistantAnswer,
            AssistantPlan,
            ToolPlanStep,
        )

        _force_terminal_console(monkeypatch)
        private_fragment = "ANSWER_SECRET_96"
        control = "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
        hostile = f"password={private_fragment} {control}"
        answer = AssistantAnswer(
            summary=hostile,
            basis=hostile,
            risks_caveats=hostile,
            tool_trace_summary=hostile,
            missing_data=[hostile],
        )
        plan = AssistantPlan(
            intent="scan_candidates",
            steps=[
                ToolPlanStep(
                    step_id="step-1",
                    tool_name="watchlist.scan",
                    arguments={"note": hostile},
                    purpose=hostile,
                    required_permission="READ_WATCHLIST",
                )
            ],
        )

        with patch(
            "vnalpha.assistant.app.AssistantApp.ask",
            return_value=(answer, plan),
        ):
            result = runner.invoke(
                app,
                ["ask", "Show watchlist", "--show-plan", "--trace"],
                color=True,
            )

        assert result.exit_code == 0
        assert private_fragment not in result.output
        assert "\x1b]8;" not in result.output
        assert "[REDACTED]" in result.output

    def test_ask_sanitizes_refusal_output(self, monkeypatch) -> None:
        from vnalpha.assistant.models import AssistantPlan, RefusalMessage

        _force_terminal_console(monkeypatch)
        private_fragment = "REFUSAL_SECRET_44"
        control = "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
        refusal = RefusalMessage(
            reason=f"password={private_fragment} {control}",
            policy_category="UNAVAILABLE_TOOL",
            suggestion=f"authorization=Bearer {private_fragment} {control}",
        )

        with patch(
            "vnalpha.assistant.app.AssistantApp.ask",
            return_value=(refusal, AssistantPlan(intent="unsupported", steps=[])),
        ):
            result = runner.invoke(app, ["ask", "Show watchlist"], color=True)

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "\x1b]8;" not in result.output


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
        # Given: the generic TUI target resolves to the current calendar day.
        from vnalpha.tui import app as tui_app_module

        monkeypatch.setattr(
            tui_app_module,
            "resolve_date",
            lambda _value: "2026-07-19",
            raising=False,
        )

        # When: the TUI is created without --date.
        tui_app = tui_app_module.VnAlphaApp()

        # Then: generic compatibility and implicit provenance are both retained.
        assert tui_app.target_date == "2026-07-19"
        assert tui_app.target_date_is_implicit is True

    def test_tui_calendar_coverage_failure_is_user_facing(self, monkeypatch) -> None:
        from vnalpha.ingestion.trading_calendar import CalendarCoverageError
        from vnalpha.tui import app as tui_app_module

        class FailingTuiApp:
            def __init__(self, **_kwargs):
                raise CalendarCoverageError("calendar coverage unavailable")

        monkeypatch.setattr(tui_app_module, "VnAlphaApp", FailingTuiApp)

        result = runner.invoke(app, ["tui"])

        assert result.exit_code == 1
        assert "Error: calendar coverage unavailable" in result.output

    def test_tui_invalid_date_error_is_redacted(self) -> None:
        private_fragment = "TUI_DATE_SECRET_17"
        control = "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"

        result = runner.invoke(
            app,
            [
                "tui",
                "--date",
                f"bad password={private_fragment} {control}",
            ],
        )

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "\x1b]8;" not in result.output
        assert "[REDACTED]" in result.output

    def test_tui_runtime_error_is_generic(self, monkeypatch) -> None:
        from vnalpha.tui import app as tui_app_module

        private_fragment = "CONTROLLED_TUI_RUN_PRIVATE_23CE"

        class FailingTuiApp:
            def __init__(self, **_kwargs):
                pass

            def run(self) -> None:
                raise RuntimeError(f"password={private_fragment}")

        monkeypatch.setattr(tui_app_module, "VnAlphaApp", FailingTuiApp)

        result = runner.invoke(app, ["tui"])

        assert result.exit_code == 1
        assert private_fragment not in result.output
        assert "Traceback" not in result.output
        assert "TUI failed to start. Check logs and retry." in result.output

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

    def test_legacy_assistant_screen_preserves_provenance_and_redacts_errors(
        self, monkeypatch
    ) -> None:
        from rich.text import Text

        from vnalpha.assistant.errors import AssistantInputValidationError
        from vnalpha.tui.screens.assistant import AssistantScreen

        class Panel:
            value = None

            def update(self, value):
                self.value = value

        answer_panel = Panel()
        plan_panel = Panel()
        screen = AssistantScreen(target_date="2026-07-19", target_date_is_implicit=True)
        monkeypatch.setattr(
            screen,
            "query_one",
            lambda selector, _type=None: (
                answer_panel if selector == "#assistant-answer" else plan_panel
            ),
        )
        private_fragment = "LEGACY_SECRET_61"
        malicious_error = (
            "Invalid date [link=https://example.invalid]bad[/link] "
            f"password={private_fragment}"
        )

        with (
            patch("vnalpha.warehouse.connection.get_connection") as get_connection,
            patch("vnalpha.warehouse.migrations.run_migrations"),
            patch("vnalpha.assistant.gateway.LLMGatewayConfig.from_env"),
            patch("vnalpha.assistant.gateway.LLMGatewayClient"),
            patch(
                "vnalpha.assistant.app.AssistantApp.ask",
                side_effect=AssistantInputValidationError(malicious_error),
            ) as ask,
        ):
            screen._process_question("Phân tích sâu mã VCB")

        ask.assert_called_once_with(
            "Phân tích sâu mã VCB",
            date="2026-07-19",
            date_is_implicit=True,
        )
        assert isinstance(answer_panel.value, Text)
        assert "Invalid date" in answer_panel.value.plain
        assert "[REDACTED]" in answer_panel.value.plain
        assert private_fragment not in answer_panel.value.plain
        assert all("link" not in str(span.style) for span in answer_panel.value.spans)
        get_connection.return_value.close.assert_called_once_with()

    def test_legacy_assistant_screen_hides_unexpected_errors(self, monkeypatch) -> None:
        from vnalpha.tui.screens.assistant import AssistantScreen

        class Panel:
            value = None

            def update(self, value):
                self.value = value

        answer_panel = Panel()
        plan_panel = Panel()
        screen = AssistantScreen(target_date="2026-07-19")
        monkeypatch.setattr(
            screen,
            "query_one",
            lambda selector, _type=None: (
                answer_panel if selector == "#assistant-answer" else plan_panel
            ),
        )
        private_fragment = "LEGACY_PROVIDER_SECRET_13"

        with (
            patch("vnalpha.warehouse.connection.get_connection") as get_connection,
            patch("vnalpha.warehouse.migrations.run_migrations"),
            patch("vnalpha.assistant.gateway.LLMGatewayConfig.from_env"),
            patch("vnalpha.assistant.gateway.LLMGatewayClient"),
            patch(
                "vnalpha.assistant.app.AssistantApp.ask",
                side_effect=RuntimeError(f"password={private_fragment}"),
            ),
        ):
            screen._process_question("Phân tích sâu mã VCB")

        assert private_fragment not in answer_panel.value.plain
        assert (
            "Assistant request failed. Check logs and retry."
            in answer_panel.value.plain
        )
        get_connection.return_value.close.assert_called_once_with()

    def test_legacy_assistant_screen_sanitizes_successful_output(
        self, monkeypatch
    ) -> None:
        from vnalpha.assistant.models import AssistantAnswer, AssistantPlan
        from vnalpha.tui.screens.assistant import AssistantScreen

        class Panel:
            value = None

            def update(self, value):
                self.value = value

        answer_panel = Panel()
        plan_panel = Panel()
        screen = AssistantScreen(target_date="2026-07-19")
        monkeypatch.setattr(
            screen,
            "query_one",
            lambda selector, _type=None: (
                answer_panel if selector == "#assistant-answer" else plan_panel
            ),
        )
        private_fragment = "LEGACY_ANSWER_SECRET_75"
        hostile = (
            f"password={private_fragment} "
            "\x1b]8;;https://example.invalid\x1b\\click\x1b]8;;\x1b\\"
        )
        answer = AssistantAnswer(
            summary=hostile,
            basis=hostile,
            risks_caveats=hostile,
            tool_trace_summary=hostile,
        )

        with (
            patch("vnalpha.warehouse.connection.get_connection"),
            patch("vnalpha.warehouse.migrations.run_migrations"),
            patch("vnalpha.assistant.gateway.LLMGatewayConfig.from_env"),
            patch("vnalpha.assistant.gateway.LLMGatewayClient"),
            patch(
                "vnalpha.assistant.app.AssistantApp.ask",
                return_value=(answer, AssistantPlan(intent="scan", steps=[])),
            ),
        ):
            screen._process_question("Phân tích sâu mã VCB")

        visible = answer_panel.value.plain + plan_panel.value.plain
        assert private_fragment not in visible
        assert "\x1b]8;" not in visible
        assert "[REDACTED]" in visible


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
