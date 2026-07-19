from __future__ import annotations

import json
from datetime import date as DateType

import duckdb
import typer

from vnalpha.core.dates import resolve_date
from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar
from vnalpha.maintenance.daily import (
    DailyMaintenanceRequest,
    DailyMaintenanceService,
    MaintenanceRunStatus,
)
from vnalpha.observability.context import set_correlation_id
from vnalpha.warehouse.connection import get_connection
from vnalpha.warehouse.migrations import run_migrations

app = typer.Typer(help="Run deterministic one-shot market maintenance.")


@app.command("daily")
def daily(
    date: str = typer.Option("today", "--date", help="Vietnam market date."),
    symbols: str | None = typer.Option(
        None, "--symbols", help="Comma-separated bounded equity symbols."
    ),
    source: str | None = typer.Option(None, "--source", help="Preferred provider."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    requested_symbols = _parse_symbols(symbols)
    resolved_date = resolve_date(date)
    is_session = VietnamSessionCalendar().is_session(
        DateType.fromisoformat(resolved_date)
    )
    conn = _maintenance_connection(ephemeral=dry_run or not is_session)
    try:
        if not dry_run and is_session:
            run_migrations(conn=conn)
        set_correlation_id()
        result = DailyMaintenanceService(conn).run(
            DailyMaintenanceRequest(
                date=date,
                symbols=requested_symbols,
                source=source,
                dry_run=dry_run,
            )
        )
        payload = result.to_dict()
        if json_output:
            typer.echo(json.dumps(payload, sort_keys=True))
        else:
            typer.echo(
                f"{result.status.value} date={result.resolved_date} "
                f"successful={len(result.successful_symbols)} "
                f"failed={len(result.failed_symbols)} "
                f"correlation_id={result.correlation_id}"
            )
        if result.status is MaintenanceRunStatus.FAILED:
            raise typer.Exit(code=1)
        if result.status is MaintenanceRunStatus.PARTIAL:
            raise typer.Exit(code=3)
    finally:
        conn.close()


def _maintenance_connection(*, ephemeral: bool) -> duckdb.DuckDBPyConnection:
    if ephemeral:
        return duckdb.connect(":memory:")
    return get_connection()


def _parse_symbols(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    symbols = tuple(item.strip() for item in value.split(","))
    if any(not item for item in symbols):
        raise typer.BadParameter("Use a comma-separated list of non-empty symbols.")
    return symbols


__all__ = ["app"]
