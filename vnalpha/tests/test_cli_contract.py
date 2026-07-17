"""CLI contract tests for Phase 5.

Tests CLI flags, universe resolution, and symbol parsing logic
without making any real network calls.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vnalpha.cli import app
from vnalpha.core.universe import parse_symbols_or_universe, resolve_universe

runner = CliRunner()


class TestCliModuleCompatibility:
    def test_cli_shim_exports_modular_app(self):
        from vnalpha.cli_app.app import app as modular_app

        assert app is modular_app

    def test_modular_app_registers_existing_command_groups(self):
        from vnalpha.cli_app.app import app as modular_app

        result = runner.invoke(modular_app, ["--help"])

        assert result.exit_code == 0
        for command_name in (
            "sync",
            "build",
            "shortlist",
            "outcome",
            "eval",
            "logs",
            "repair",
            "deploy",
        ):
            assert command_name in result.output


# ---------------------------------------------------------------------------
# CLI flag contract tests
# ---------------------------------------------------------------------------


class TestSyncOHLCVFlags:
    def test_sync_ohlcv_accepts_universe_flag(self):
        """sync ohlcv --help exits 0 and lists --universe option."""
        result = runner.invoke(app, ["sync", "ohlcv", "--help"])
        assert result.exit_code == 0, (
            f"Unexpected exit code: {result.exit_code}\n{result.output}"
        )
        assert "--universe" in result.output, (
            f"--universe not found in help output:\n{result.output}"
        )

    def test_sync_ohlcv_accepts_symbols_flag(self):
        """sync ohlcv --help exits 0 and lists --symbols option."""
        result = runner.invoke(app, ["sync", "ohlcv", "--help"])
        assert result.exit_code == 0, (
            f"Unexpected exit code: {result.exit_code}\n{result.output}"
        )
        assert "--symbols" in result.output, (
            f"--symbols not found in help output:\n{result.output}"
        )

    def test_sync_ohlcv_unknown_universe_raises_value_error(self):
        """resolve_universe('UNKNOWN_XYZ') raises ValueError with 'Unknown universe'."""
        with pytest.raises(ValueError, match="Unknown universe"):
            resolve_universe("UNKNOWN_XYZ")

    def test_sync_index_command_exists(self):
        """sync index --help exits 0 and lists --symbol option."""
        result = runner.invoke(app, ["sync", "index", "--help"])
        assert result.exit_code == 0, (
            f"Unexpected exit code: {result.exit_code}\n{result.output}"
        )
        assert "--symbol" in result.output, (
            f"--symbol not found in sync index help:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# Universe resolver tests
# ---------------------------------------------------------------------------


class TestResolveUniverse:
    def test_vn30_resolves_to_symbols(self):
        """resolve_universe('VN30') returns at least 30 symbols and includes 'FPT'."""
        symbols = resolve_universe("VN30")
        assert len(symbols) >= 30, f"VN30 resolved to only {len(symbols)} symbols"
        assert "FPT" in symbols, f"FPT not in VN30: {symbols}"

    def test_vn30_case_insensitive(self):
        """resolve_universe is case-insensitive: 'vn30' == 'VN30'."""
        lower = resolve_universe("vn30")
        upper = resolve_universe("VN30")
        assert lower == upper, (
            f"resolve_universe('vn30') != resolve_universe('VN30'): {lower} vs {upper}"
        )

    def test_unknown_universe_raises_value_error(self):
        """resolve_universe('NONEXISTENT') raises ValueError."""
        with pytest.raises(ValueError):
            resolve_universe("NONEXISTENT")


# ---------------------------------------------------------------------------
# parse_symbols_or_universe tests
# ---------------------------------------------------------------------------


class TestParseSymbolsOrUniverse:
    def test_symbols_takes_precedence_over_universe(self):
        """When --symbols is provided, it takes precedence over --universe."""
        result = parse_symbols_or_universe("FPT,VNM", "VN30")
        assert result == ["FPT", "VNM"], f"Expected ['FPT', 'VNM'], got {result}"

    def test_universe_used_when_no_symbols(self):
        """When --symbols is None, resolve the named universe."""
        result = parse_symbols_or_universe(None, "VN30")
        assert result is not None, "Expected VN30 symbol list, got None"
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) >= 30, f"VN30 resolved to only {len(result)} symbols"

    def test_no_symbols_no_universe_returns_none(self):
        """When both --symbols and --universe are None, returns None."""
        result = parse_symbols_or_universe(None, None)
        assert result is None, f"Expected None, got {result}"

    def test_symbols_parsed_as_uppercase(self):
        """Symbols are normalised to uppercase."""
        result = parse_symbols_or_universe("fpt,vnm", None)
        assert result == ["FPT", "VNM"], (
            f"Expected uppercased ['FPT', 'VNM'], got {result}"
        )

    def test_symbols_whitespace_stripped(self):
        """Whitespace around comma-separated symbols is stripped."""
        result = parse_symbols_or_universe(" FPT , VNM ", None)
        assert result == ["FPT", "VNM"], f"Expected ['FPT', 'VNM'], got {result}"
