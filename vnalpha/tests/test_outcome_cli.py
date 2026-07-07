"""CLI contract tests for outcome commands."""

from typer.testing import CliRunner

from vnalpha.cli import app

runner = CliRunner()


class TestOutcomeCommandHelp:
    def test_outcome_help_exists(self):
        result = runner.invoke(app, ["outcome", "--help"])
        assert result.exit_code == 0
        assert "outcome" in result.output.lower() or "Outcome" in result.output

    def test_outcome_evaluate_help(self):
        result = runner.invoke(app, ["outcome", "evaluate", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output

    def test_outcome_candidates_help(self):
        result = runner.invoke(app, ["outcome", "candidates", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output
        assert "--horizon" in result.output

    def test_outcome_watchlist_help(self):
        result = runner.invoke(app, ["outcome", "watchlist", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output

    def test_outcome_buckets_help(self):
        result = runner.invoke(app, ["outcome", "buckets", "--help"])
        assert result.exit_code == 0
        assert "--horizon" in result.output

    def test_outcome_setups_help(self):
        result = runner.invoke(app, ["outcome", "setups", "--help"])
        assert result.exit_code == 0
        assert "--horizon" in result.output

    def test_outcome_risks_help(self):
        result = runner.invoke(app, ["outcome", "risks", "--help"])
        assert result.exit_code == 0
        assert "--horizon" in result.output

    def test_outcome_report_help(self):
        result = runner.invoke(app, ["outcome", "report", "--help"])
        assert result.exit_code == 0
        assert "--horizon" in result.output


class TestOutcomeLanguageBoundary:
    def test_no_buy_sell_in_help(self):
        for cmd in [
            "evaluate",
            "candidates",
            "watchlist",
            "buckets",
            "setups",
            "risks",
            "report",
        ]:
            result = runner.invoke(app, ["outcome", cmd, "--help"])
            assert "buy signal" not in result.output.lower()
            assert "sell signal" not in result.output.lower()
            assert "place order" not in result.output.lower()

    def test_evaluate_requires_date_or_range(self):
        result = runner.invoke(app, ["outcome", "evaluate"])
        # Should exit non-zero without --date or --from/--to
        assert result.exit_code != 0
