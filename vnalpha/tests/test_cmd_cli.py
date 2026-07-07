"""CLI contract tests for 'vnalpha cmd' (Tasks 6.1-6.5)."""

from __future__ import annotations

from typer.testing import CliRunner

from vnalpha.cli import app

runner = CliRunner()


class TestCmdHelp:
    def test_cmd_help_option(self):
        result = runner.invoke(app, ["cmd", "--help"])
        assert result.exit_code == 0
        assert (
            "slash command" in result.output.lower() or "cmd" in result.output.lower()
        )

    def test_cmd_help_command(self):
        result = runner.invoke(app, ["cmd", "/help"])
        assert result.exit_code == 0
        assert "/scan" in result.output or "scan" in result.output

    def test_cmd_unknown_returns_nonzero(self):
        result = runner.invoke(app, ["cmd", "/nonexistent_xyz"])
        assert result.exit_code != 0

    def test_cmd_invalid_syntax_returns_nonzero(self):
        result = runner.invoke(app, ["cmd", "no-slash"])
        assert result.exit_code != 0

    def test_cmd_scan_runs(self):
        """vnalpha cmd /scan should run without error (empty watchlist ok)."""
        result = runner.invoke(app, ["cmd", "/scan --date 2000-01-01"])
        assert result.exit_code == 0

    def test_cmd_history_runs(self):
        result = runner.invoke(app, ["cmd", "/history --limit 5"])
        assert result.exit_code == 0

    def test_cmd_explain_missing_score_graceful(self):
        """vnalpha cmd /explain SYMBOL with no data should succeed (graceful empty)."""
        result = runner.invoke(app, ["cmd", "/explain NOSYM --date 2000-01-01"])
        assert result.exit_code == 0

    def test_cmd_validation_error_nonzero(self):
        """vnalpha cmd /compare with no symbols returns validation error (exit 1)."""
        result = runner.invoke(app, ["cmd", "/compare"])
        assert result.exit_code != 0

    def test_cmd_date_override(self):
        """--date flag overrides the date in the command."""
        result = runner.invoke(app, ["cmd", "/scan", "--date", "2000-01-01"])
        assert result.exit_code == 0

    def test_cmd_session_persisted(self, tmp_path):
        """Each cmd invocation should persist a research_session row."""
        import duckdb

        from vnalpha.warehouse.migrations import run_migrations
        from vnalpha.warehouse.session_repo import list_research_sessions

        conn = duckdb.connect(":memory:")
        run_migrations(conn=conn)

        # We test the persistence logic directly here (not through CLI which uses its own conn)
        from vnalpha.warehouse.session_repo import (
            create_research_session,
            finish_research_session,
        )

        sid = create_research_session(
            conn, surface="cli", command_text="/help", command_name="help"
        )
        finish_research_session(conn, sid, status="SUCCESS")
        sessions = list_research_sessions(conn, limit=5)
        assert len(sessions) == 1
        assert sessions[0]["status"] == "SUCCESS"
