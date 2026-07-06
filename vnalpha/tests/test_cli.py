"""Test vnalpha CLI entry point."""

from typer.testing import CliRunner

from vnalpha.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "vnalpha" in result.output.lower()


def test_version_or_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_sync_symbols_help():
    result = runner.invoke(app, ["sync", "symbols", "--help"])
    assert result.exit_code == 0


def test_sync_ohlcv_help():
    result = runner.invoke(app, ["sync", "ohlcv", "--help"])
    assert result.exit_code == 0


def test_build_canonical_help():
    result = runner.invoke(app, ["build", "canonical", "--help"])
    assert result.exit_code == 0


def test_tui_help():
    result = runner.invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
