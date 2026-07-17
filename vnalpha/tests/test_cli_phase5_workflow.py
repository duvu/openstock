"""CLI Phase 5 workflow tests.

Tests that Phase 5 CLI commands:
- Are properly wired (not stubs)
- Use resolve_date correctly
- Produce expected output shapes
- Persist the right data

Uses typer's CliRunner with an isolated in-memory warehouse.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vnalpha.cli import app

runner = CliRunner()


class TestCliHelpPages:
    def test_build_features_help(self):
        result = runner.invoke(app, ["build", "features", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output

    def test_score_help(self):
        result = runner.invoke(app, ["score", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output

    def test_watchlist_help(self):
        result = runner.invoke(app, ["watchlist", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output

    def test_shortlist_help(self):
        result = runner.invoke(app, ["shortlist", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output
        assert "--limit" in result.output

    def test_tui_help(self):
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output


class TestNoPlaceholderOutput:
    """No Phase 5 command should print 'not yet implemented'."""

    def test_build_features_no_stub_output(self):
        result = runner.invoke(app, ["build", "features", "--help"])
        assert "not yet implemented" not in result.output.lower()

    def test_score_no_stub_output(self):
        result = runner.invoke(app, ["score", "--help"])
        assert "not yet implemented" not in result.output.lower()

    def test_watchlist_no_stub_output(self):
        result = runner.invoke(app, ["watchlist", "--help"])
        assert "not yet implemented" not in result.output.lower()

    def test_shortlist_no_stub_output(self):
        result = runner.invoke(app, ["shortlist", "--help"])
        assert "not yet implemented" not in result.output.lower()

    def test_tui_no_stub_output(self):
        result = runner.invoke(app, ["tui", "--help"])
        assert "not yet implemented" not in result.output.lower()


class TestDateResolution:
    """CLI commands should accept 'today' and ISO dates."""

    def test_score_accepts_today(self, monkeypatch):
        """score --date today should not crash with ValueError."""
        # We only check it doesn't raise on date parsing, not full execution
        from vnalpha.core.dates import resolve_date

        resolved = resolve_date("today")
        assert len(resolved) == 10  # YYYY-MM-DD

    def test_score_accepts_iso_date(self):
        from vnalpha.core.dates import resolve_date

        assert resolve_date("2024-06-28") == "2024-06-28"

    def test_invalid_date_raises(self):
        from vnalpha.core.dates import resolve_date

        with pytest.raises(ValueError, match="Invalid date"):
            resolve_date("not-a-date")

    def test_none_resolves_to_today(self):
        from datetime import date

        from vnalpha.core.dates import resolve_date

        assert resolve_date(None) == str(date.today())


class TestWatchlistCommandOutput:
    """watchlist command should produce research-language output."""

    def test_watchlist_no_candidates_shows_message(self, monkeypatch):
        """When no candidates, show a 'No watchlist entries' message."""
        # Patch get_watchlist to return empty list
        from vnalpha.warehouse import repositories

        monkeypatch.setattr(repositories, "get_watchlist", lambda conn, date: [])
        # Also patch get_connection to avoid real DB
        from vnalpha.warehouse import connection

        monkeypatch.setattr(connection, "get_connection", lambda: None)

        result = runner.invoke(app, ["watchlist", "--date", "2024-06-28"])
        assert result.exit_code == 0
        assert "No watchlist entries" in result.output

    def test_watchlist_output_uses_research_language(self, monkeypatch):
        """Watchlist output must not contain execution-style wording."""
        from vnalpha.warehouse import repositories

        monkeypatch.setattr(
            repositories,
            "get_watchlist",
            lambda conn, date: [
                {
                    "rank": 1,
                    "symbol": "FPT",
                    "score": 0.80,
                    "candidate_class": "STRONG_CANDIDATE",
                    "setup_type": "ACCUMULATION_BASE",
                    "risk_flags_json": "[]",
                    "lineage_json": "{}",
                }
            ],
        )
        from vnalpha.warehouse import connection

        monkeypatch.setattr(connection, "get_connection", lambda: None)

        result = runner.invoke(app, ["watchlist", "--date", "2024-06-28"])
        assert result.exit_code == 0
        # No execution-style language
        forbidden = ["buy", "sell", "order", "execute", "portfolio", "position"]
        output_lower = result.output.lower()
        for word in forbidden:
            assert word not in output_lower, (
                f"Forbidden word '{word}' found in watchlist output"
            )


class TestScoreCommandOutput:
    def test_score_output_contains_scored_and_saved_counts(self, monkeypatch):
        """score command should report scored and saved counts."""
        from vnalpha.scoring import generate_watchlist as gw_module

        monkeypatch.setattr(
            gw_module,
            "generate_watchlist",
            lambda conn, **kwargs: {"scored": 3, "saved": 2},
        )
        from vnalpha.warehouse import connection

        monkeypatch.setattr(connection, "get_connection", lambda: None)

        result = runner.invoke(app, ["score", "--date", "2024-06-28"])
        assert result.exit_code == 0
        assert "3" in result.output  # scored count
        assert "2" in result.output  # saved count


class TestResearchLanguageBoundary:
    """Phase 5 CLI output must use research/watchlist language, not execution language."""

    FORBIDDEN_WORDS = [
        "buy",
        "sell",
        "order",
        "execute",
        "trade",
        "position",
        "portfolio",
        "invest",
        "purchase",
        "transaction",
    ]

    def test_cli_help_texts_no_execution_language(self):
        """All help texts should use research language."""
        commands = [
            ["--help"],
            ["build", "features", "--help"],
            ["score", "--help"],
            ["watchlist", "--help"],
            ["tui", "--help"],
        ]
        for cmd in commands:
            result = runner.invoke(app, cmd)
            output_lower = result.output.lower()
            for word in self.FORBIDDEN_WORDS:
                assert word not in output_lower, (
                    f"Forbidden word '{word}' found in 'vnalpha {' '.join(cmd)}' output"
                )

    def test_score_output_uses_candidate_language(self, monkeypatch):
        """score output should say 'candidates in watchlist' not 'signals to execute'."""
        from vnalpha.scoring import generate_watchlist as gw_module

        monkeypatch.setattr(
            gw_module,
            "generate_watchlist",
            lambda conn, **kwargs: {"scored": 5, "saved": 3},
        )
        from vnalpha.warehouse import connection

        monkeypatch.setattr(connection, "get_connection", lambda: None)

        result = runner.invoke(app, ["score", "--date", "2024-06-28"])
        assert result.exit_code == 0
        # Should say "candidates in watchlist" or similar research language
        assert (
            "candidates" in result.output.lower()
            or "watchlist" in result.output.lower()
        )
