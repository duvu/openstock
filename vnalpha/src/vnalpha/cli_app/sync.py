from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle

app = typer.Typer(help="Sync data from vnstock-service into the warehouse.")


@app.command("symbols")
def sync_symbols_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Preferred provider"),
):
    """Sync symbol master from vnstock-service."""
    set_correlation_id()
    with command_lifecycle("sync symbols"):
        from vnalpha.ingestion.sync_symbols import sync_symbols
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        result = sync_symbols(conn, source=source)
        typer.echo(f"Synced {result['synced']} symbols (errors: {result['errors']})")


@app.command("ohlcv")
def sync_ohlcv_cmd(
    symbols: Optional[str] = typer.Option(
        None,
        "--symbols",
        help="Comma-separated symbols (takes precedence over --universe)",
    ),
    universe: Optional[str] = typer.Option(
        None, "--universe", help="Named universe (e.g. VN30). Resolved to symbol list."
    ),
    start: Optional[str] = typer.Option(None, "--start"),
    end: Optional[str] = typer.Option(None, "--end"),
    interval: str = typer.Option("1D", "--interval"),
    source: Optional[str] = typer.Option(None, "--source"),
):
    """Sync equity OHLCV data from vnstock-service.

    Resolution order: --symbols > --universe > all active symbols.
    """
    set_correlation_id()
    with command_lifecycle("sync ohlcv"):
        from vnalpha.core.universe import parse_symbols_or_universe
        from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        try:
            resolved = parse_symbols_or_universe(symbols, universe)
        except ValueError as err:
            typer.echo(f"Error: {err}", err=True)
            raise typer.Exit(code=1) from err

        result = sync_ohlcv(
            conn,
            universe=resolved,
            start=start,
            end=end,
            interval=interval,
            source=source,
        )
        typer.echo(
            f"OHLCV sync complete: {result['inserted']} inserted, {result['skipped']} skipped"
        )


@app.command("index")
def sync_index_cmd(
    symbol: str = typer.Option(
        "VNINDEX", "--symbol", help="Index symbol (e.g. VNINDEX)"
    ),
    start: Optional[str] = typer.Option(None, "--start"),
    end: Optional[str] = typer.Option(None, "--end"),
    interval: str = typer.Option("1D", "--interval"),
    source: Optional[str] = typer.Option(None, "--source"),
):
    """Sync index/benchmark OHLCV data from vnstock-service.

    Example: vnalpha sync index --symbol VNINDEX --start 2024-01-01
    """
    set_correlation_id()
    with command_lifecycle("sync index"):
        from vnalpha.ingestion.sync_index import sync_index_ohlcv
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        result = sync_index_ohlcv(
            conn, symbol=symbol, start=start, end=end, interval=interval, source=source
        )
        typer.echo(
            f"Index sync complete ({symbol}): {result['inserted']} inserted, {result['skipped']} skipped"
        )
