from __future__ import annotations

import json
import sys
from datetime import date as DateType, datetime, timezone

import duckdb
import typer

from vnalpha.core.dates import resolve_date
from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar
from vnalpha.maintenance.daily import (
    DailyMaintenanceRequest,
    DailyMaintenanceService,
    MaintenanceRunStatus,
)
from vnalpha.maintenance.ledger import persist_maintenance_run
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
        started_at = datetime.now(timezone.utc)
        result = DailyMaintenanceService(conn).run(
            DailyMaintenanceRequest(
                date=date,
                symbols=requested_symbols,
                source=source,
                dry_run=dry_run,
            )
        )
        completed_at = datetime.now(timezone.utc)

        # Persist to ledger for real sessions (not dry-run or NOOP)
        if not dry_run and result.status != MaintenanceRunStatus.NOOP:
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            software_version = f"python-{python_version}"
            calendar_version = VietnamSessionCalendar().version
            persist_maintenance_run(
                conn,
                result,
                started_at=started_at,
                completed_at=completed_at,
                software_version=software_version,
                calendar_version=calendar_version,
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


@app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query the latest maintenance run status and recent failures."""
    from vnalpha.maintenance.ledger import (
        get_failed_maintenance_stages,
        get_latest_maintenance_run,
    )

    conn = get_connection()
    try:
        latest = get_latest_maintenance_run(conn)
        failed_stages = get_failed_maintenance_stages(conn, limit=5)

        if json_output:
            typer.echo(
                json.dumps(
                    {"latest_run": latest, "recent_failed_stages": failed_stages},
                    sort_keys=True,
                )
            )
        else:
            if latest:
                typer.echo(f"Latest Run: {latest['run_id']}")
                typer.echo(f"  Status: {latest['status']}")
                typer.echo(f"  Date: {latest['resolved_date']}")
                typer.echo(f"  Completed: {latest['completed_at']}")
                typer.echo(
                    f"  Symbols: {latest['successful_symbol_count']}/{latest['requested_symbol_count']} successful"
                )
                typer.echo(f"  Duration: {latest['duration_seconds']:.1f}s")
            else:
                typer.echo("No maintenance runs found.")

            if failed_stages:
                typer.echo(f"\nRecent Failed Stages ({len(failed_stages)}):")
                for stage in failed_stages:
                    typer.echo(
                        f"  {stage['stage_name']} ({stage['status']}) "
                        f"- {stage['resolved_date']} - {len(stage['failures'])} failures"
                    )
    finally:
        conn.close()


__all__ = ["app"]
