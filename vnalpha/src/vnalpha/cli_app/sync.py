from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    DataProvisioningService,
    DataProvisioningValidationError,
    ProvisioningStatus,
)
from vnalpha.observability.commands import command_lifecycle

app = typer.Typer(help="Sync data from vnstock-service into the warehouse.")


@app.command("symbols")
def sync_symbols_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Preferred provider"),
    authoritative: bool = typer.Option(
        False,
        "--authoritative",
        help="Reconcile unseen symbols only after a complete authoritative source snapshot",
    ),
):
    """Sync symbol master from vnstock-service."""
    set_correlation_id()
    with command_lifecycle("sync symbols"):
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        result = _execute(
            conn,
            DataProvisioningRequest(
                "download",
                "symbols",
                source=source,
                authoritative_snapshot=authoritative,
            ),
        )
        typer.echo(
            f"Synced {result.counts['synced']} symbols (errors: {result.counts['errors']})"
        )


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
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        try:
            resolved = parse_symbols_or_universe(symbols, universe)
        except ValueError as err:
            typer.echo(f"Error: {err}", err=True)
            raise typer.Exit(code=1) from err

        conn = get_connection()
        run_migrations(conn=conn)
        result = _execute(
            conn,
            DataProvisioningRequest(
                "download",
                "ohlcv",
                symbols=tuple(resolved) if resolved is not None else None,
                allow_all_symbols=resolved is None,
                start=start,
                end=end,
                source=source,
                interval=interval,
            ),
            exit_on_failure=False,
        )
        typer.echo(
            f"OHLCV sync complete: {result.counts['inserted']} inserted, {result.counts['skipped']} skipped"
        )
        for symbol_result in result.symbol_results:
            if symbol_result.status.value not in {"SUCCESS", "SKIPPED"}:
                typer.echo(
                    f"{symbol_result.symbol}: {symbol_result.status.value}"
                    + (f" - {symbol_result.message}" if symbol_result.message else "")
                )
                if symbol_result.remediation:
                    typer.echo(symbol_result.remediation)
        if result.status is ProvisioningStatus.FAILED:
            typer.echo(result.error or "OHLCV sync did not complete.", err=True)
            raise typer.Exit(code=1)


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
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        result = _execute(
            conn,
            DataProvisioningRequest(
                "download",
                "index",
                symbol=symbol,
                start=start,
                end=end,
                source=source,
                interval=interval,
            ),
        )
        typer.echo(
            f"Index sync complete ({symbol}): {result.counts['inserted']} inserted, {result.counts['skipped']} skipped"
        )


@app.command("corporate-actions")
def sync_corporate_actions_cmd(
    symbol: str = typer.Argument(..., help="Equity symbol."),
    start: Optional[str] = typer.Option(None, "--start"),
    end: Optional[str] = typer.Option(None, "--end"),
    source: Optional[str] = typer.Option(None, "--source"),
):
    """Sync bounded corporate-action evidence without calculating adjusted prices."""
    from vnalpha.ingestion.corporate_actions import sync_corporate_actions
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise typer.BadParameter("symbol must not be empty")
    set_correlation_id()
    with command_lifecycle("sync corporate-actions"):
        conn = get_connection()
        run_migrations(conn=conn)
        result = sync_corporate_actions(
            conn,
            symbol=normalized_symbol,
            start=start,
            end=end,
            source=source,
        )
        typer.echo(
            "Corporate-action sync complete: "
            f"{result.get('canonical_inserted', 0)} inserted, "
            f"{result.get('revised', 0)} revised, "
            f"{result.get('quarantined', 0)} quarantined"
        )
        if result["status"] == "FAILED":
            raise typer.Exit(code=1)


def _execute(
    conn, request: DataProvisioningRequest, *, exit_on_failure: bool = True
) -> DataProvisioningResult:
    try:
        result = DataProvisioningService(conn).execute(request)
    except DataProvisioningValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if result.status is ProvisioningStatus.FAILED and exit_on_failure:
        typer.echo(result.error or "Data provisioning did not complete.", err=True)
        raise typer.Exit(code=1)
    return result
