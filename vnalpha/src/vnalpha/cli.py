"""vnalpha CLI entry point."""
from __future__ import annotations

from typing import Optional

import typer

app = typer.Typer(name="vnalpha", help="Alpha discovery research CLI.")

# ---------------------------------------------------------------------------
# sync sub-app
# ---------------------------------------------------------------------------
sync_app = typer.Typer(help="Sync data from vnstock-service into the warehouse.")
app.add_typer(sync_app, name="sync")


@sync_app.command("symbols")
def sync_symbols_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Preferred provider"),
):
    """Sync symbol master from vnstock-service."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.ingestion.sync_symbols import sync_symbols
    conn = get_connection()
    run_migrations(conn=conn)
    result = sync_symbols(conn, source=source)
    typer.echo(f"Synced {result['synced']} symbols (errors: {result['errors']})")


@sync_app.command("ohlcv")
def sync_ohlcv_cmd(
    symbols: Optional[str] = typer.Option(None, "--symbols", help="Comma-separated symbols, default: all active"),
    start: Optional[str] = typer.Option(None, "--start"),
    end: Optional[str] = typer.Option(None, "--end"),
    interval: str = typer.Option("1D", "--interval"),
    source: Optional[str] = typer.Option(None, "--source"),
):
    """Sync OHLCV data from vnstock-service."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
    conn = get_connection()
    run_migrations(conn=conn)
    universe = symbols.split(",") if symbols else None
    result = sync_ohlcv(conn, universe=universe, start=start, end=end, interval=interval, source=source)
    typer.echo(f"OHLCV sync complete: {result['inserted']} inserted, {result['skipped']} skipped")


# ---------------------------------------------------------------------------
# build sub-app
# ---------------------------------------------------------------------------
build_app = typer.Typer(help="Build derived datasets from raw warehouse data.")
app.add_typer(build_app, name="build")


@build_app.command("canonical")
def build_canonical_cmd(
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    interval: str = typer.Option("1D", "--interval"),
):
    """Build canonical OHLCV from raw data."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
    conn = get_connection()
    result = build_canonical_ohlcv(conn, symbol=symbol, interval=interval)
    typer.echo(f"Canonical build complete: {result['upserted']} rows")


@build_app.command("features")
def build_features(
    date: str = typer.Option("today", help="Reference date (YYYY-MM-DD or 'today')."),
) -> None:
    """Compute technical features for the given date."""
    typer.echo("build features: not yet implemented")


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------


@app.command("init")
def init() -> None:
    """Initialize the local DuckDB warehouse."""
    typer.echo("Initializing warehouse...")
    from vnalpha.warehouse import migrations

    migrations.run_migrations()


@app.command("score")
def score(
    date: str = typer.Option("today", help="Reference date (YYYY-MM-DD or 'today')."),
) -> None:
    """Score candidate setups for the given date."""
    typer.echo("score: not yet implemented")


@app.command("watchlist")
def watchlist(
    date: str = typer.Option("today", help="Reference date (YYYY-MM-DD or 'today')."),
) -> None:
    """Show the daily watchlist for the given date."""
    typer.echo("watchlist: not yet implemented")


@app.command("tui")
def tui() -> None:
    """Launch the interactive TUI watchlist."""
    typer.echo("tui: not yet implemented")
