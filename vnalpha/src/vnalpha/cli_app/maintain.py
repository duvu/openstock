from __future__ import annotations

import json
from datetime import datetime, timezone

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
from vnalpha.maintenance.software_identity import resolve_software_identity
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
    """Run one maintenance invocation and persist every non-dry-run result."""
    requested_symbols = _parse_symbols(symbols)
    conn = _maintenance_connection(ephemeral=dry_run)
    try:
        if not dry_run:
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

        if not dry_run:
            identity = resolve_software_identity()
            persist_maintenance_run(
                conn,
                result,
                started_at=started_at,
                completed_at=completed_at,
                software_version=identity.display,
                package_version=identity.package_version,
                source_commit=identity.source_commit,
                tree_state=identity.tree_state,
                calendar_version=VietnamSessionCalendar().version,
                source_policy=_resolve_source_policy(source),
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


def _resolve_source_policy(requested_source: str | None) -> dict[str, object]:
    """Resolve and record the per-dataset source policy for this invocation."""
    from vnalpha.data_provisioning.source_policy import get_default_resolver

    resolver = get_default_resolver()
    normalized = requested_source.strip().lower() if requested_source else None
    datasets = (
        "reference.symbols",
        "equity.ohlcv",
        "index.ohlcv",
        "reference.index_membership_snapshot",
        "reference.sector_membership_snapshot",
    )
    policy: dict[str, object] = {}
    for dataset in datasets:
        resolved = resolver.resolve(dataset, requested_source=normalized)
        policy[dataset] = {
            "source": resolved.source,
            "mode": resolved.mode.value,
            "fallback_allowed": resolved.fallback_allowed,
            "rationale": resolved.rationale,
        }
    return policy


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
                    f"  Symbols: {latest['successful_symbol_count']}/"
                    f"{latest['requested_symbol_count']} successful"
                )
                typer.echo(f"  Duration: {latest['duration_seconds']:.1f}s")
                typer.echo(
                    "  Software: "
                    f"{latest.get('package_version') or latest['software_version']} "
                    f"commit={latest.get('source_commit') or 'unknown'}"
                )
            else:
                typer.echo("No maintenance runs found.")

            if failed_stages:
                typer.echo(f"\nRecent Failed Stages ({len(failed_stages)}):")
                for stage in failed_stages:
                    typer.echo(
                        f"  {stage['stage_name']} ({stage['status']}) "
                        f"- {stage['resolved_date']} - "
                        f"{len(stage['failures'])} failures"
                    )
    finally:
        conn.close()


@app.command("readiness")
def readiness(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Report per-dataset readiness and the resolved source policy."""
    from vnalpha.data_availability.dataset_readiness import check_dataset_readiness
    from vnalpha.data_provisioning.source_policy import get_default_resolver

    datasets = (
        "reference.symbols",
        "equity.ohlcv",
        "index.ohlcv",
        "reference.index_membership_snapshot",
        "reference.sector_membership_snapshot",
    )
    resolver = get_default_resolver()
    conn = get_connection()
    try:
        report = []
        for dataset in datasets:
            result = check_dataset_readiness(conn, dataset)
            resolved = resolver.resolve(dataset)
            report.append(
                {
                    "dataset": dataset,
                    "status": result.status.value,
                    "auto_providers": list(result.auto_providers),
                    "explicit_providers": list(result.explicit_providers),
                    "rejection_reasons": list(result.rejection_reasons),
                    "resolved_source": resolved.source,
                    "selection_mode": resolved.mode.value,
                    "fallback_allowed": resolved.fallback_allowed,
                    "message": result.message,
                }
            )
    finally:
        conn.close()

    if json_output:
        typer.echo(json.dumps({"datasets": report}, sort_keys=True))
    else:
        for entry in report:
            typer.echo(
                f"{entry['dataset']}: {entry['status']} "
                f"(source={entry['resolved_source'] or 'auto'}, "
                f"mode={entry['selection_mode']})"
            )
            if entry["explicit_providers"]:
                typer.echo(f"  explicit-only: {', '.join(entry['explicit_providers'])}")
            if entry["rejection_reasons"]:
                typer.echo(f"  rejected: {', '.join(entry['rejection_reasons'])}")


@app.command("proof")
def proof(
    sessions: int = typer.Option(
        10, "--sessions", help="Required consecutive session count."
    ),
    rerun_dates: int = typer.Option(
        2, "--rerun-dates", help="Required number of dates with a same-date rerun."
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate persisted ledger evidence for issue #255."""
    from vnalpha.maintenance.ledger import collect_operational_proof

    conn = get_connection()
    try:
        report = collect_operational_proof(
            conn,
            required_sessions=sessions,
            required_rerun_dates=rerun_dates,
        )
    finally:
        conn.close()

    if json_output:
        typer.echo(json.dumps(report, sort_keys=True))
    else:
        typer.echo(
            f"Operational proof: {report['distinct_sessions_recorded']}/"
            f"{report['required_sessions']} sessions"
        )
        typer.echo(
            f"  consecutive_market_sessions: "
            f"{report['consecutive_market_sessions']}"
        )
        typer.echo(f"  identity_complete: {report['identity_complete']}")
        typer.echo(
            f"  source_policy_complete: {report['source_policy_complete']}"
        )
        typer.echo(
            f"  same-date reruns: {len(report['same_date_rerun_dates'])}/"
            f"{report['required_rerun_dates']}"
        )
        if report["missing_session_dates"]:
            typer.echo(
                f"  missing sessions: {', '.join(report['missing_session_dates'])}"
            )
        if report["calendar_error"]:
            typer.echo(f"  calendar error: {report['calendar_error']}")
    if not report["has_required_sessions"]:
        raise typer.Exit(code=1)


__all__ = ["app"]
