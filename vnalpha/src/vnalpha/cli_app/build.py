from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.dates import resolve_date
from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle

app = typer.Typer(help="Build derived datasets from raw warehouse data.")


@app.command("canonical")
def build_canonical_cmd(
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    interval: str = typer.Option("1D", "--interval"),
):
    """Build canonical OHLCV from raw data."""
    set_correlation_id()
    with command_lifecycle("build canonical"):
        from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        result = build_canonical_ohlcv(conn, symbol=symbol, interval=interval)
        typer.echo(
            f"Canonical build complete: {result['upserted']} rows, {result.get('rejected', 0)} symbols rejected"
        )


@app.command("features")
def build_features_cmd(
    date: str = typer.Option(
        "today", "--date", help="Reference date (YYYY-MM-DD or 'today')."
    ),
    symbols: Optional[str] = typer.Option(
        None, "--symbols", help="Comma-separated symbols, default: all."
    ),
    benchmark: str = typer.Option(
        "VNINDEX", "--benchmark", help="Benchmark symbol for relative strength."
    ),
) -> None:
    """Compute technical features for all symbols on the given date."""
    set_correlation_id()
    with command_lifecycle("build features"):
        from vnalpha.features.build_features import build_features
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        target_date = resolve_date(date, conn=conn)
        universe = symbols.split(",") if symbols else None

        result = build_features(
            conn, target_date=target_date, universe=universe, benchmark_symbol=benchmark
        )
        typer.echo(
            f"Features built: {result['built']} symbols, skipped: {result['skipped']}"
        )
