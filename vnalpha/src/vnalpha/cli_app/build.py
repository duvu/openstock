from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningService,
    ProvisioningStatus,
)
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
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        result = _execute(
            conn,
            DataProvisioningRequest(
                "build", "canonical", symbol=symbol, interval=interval
            ),
        )
        typer.echo(
            f"Canonical build complete: {result.counts['upserted']} rows, {result.counts['rejected']} symbols rejected"
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
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        result = _execute(
            conn,
            DataProvisioningRequest(
                "build",
                "features",
                symbols=tuple(symbols.split(",")) if symbols else None,
                allow_all_symbols=symbols is None,
                date=date,
            ),
        )
        typer.echo(
            f"Features built: {result.counts['built']} symbols, skipped: {result.counts['skipped']}"
        )


@app.command("market-regime")
def build_market_regime_cmd(
    date: str = typer.Option(..., "--date", help="Exact as-of date (YYYY-MM-DD)."),
) -> None:
    """Build one bounded persisted market-regime snapshot."""
    set_correlation_id()
    with command_lifecycle("build market-regime"):
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        result = _execute(
            conn, DataProvisioningRequest("build", "market-regime", date=date)
        )
        typer.echo(
            f"Market regime built: {result.resolved_date} ({result.status.value})"
        )


@app.command("sector-strength")
def build_sector_strength_cmd(
    date: str = typer.Option(..., "--date", help="Exact as-of date (YYYY-MM-DD)."),
) -> None:
    """Build bounded persisted sector-strength snapshots for one date."""
    set_correlation_id()
    with command_lifecycle("build sector-strength"):
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        result = _execute(
            conn, DataProvisioningRequest("build", "sector-strength", date=date)
        )
        typer.echo(
            f"Sector strength built: {result.counts['sectors']} sectors ({result.status.value})"
        )


def _execute(conn, request: DataProvisioningRequest):
    result = DataProvisioningService(conn).execute(request)
    if result.status is ProvisioningStatus.FAILED:
        typer.echo(result.error or "Data provisioning did not complete.", err=True)
        raise typer.Exit(code=1)
    return result
