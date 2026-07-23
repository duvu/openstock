from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import duckdb
import typer

from vnalpha.data_availability.dataset_readiness import check_dataset_readiness
from vnalpha.data_provisioning.source_policy import get_default_resolver
from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar
from vnalpha.maintenance.daily import (
    DailyMaintenanceRequest,
    DailyMaintenanceService,
    MaintenanceRunStatus,
)
from vnalpha.maintenance.ledger import (
    collect_operational_proof,
    get_failed_maintenance_stages,
    get_latest_maintenance_run,
    persist_maintenance_run,
)
from vnalpha.maintenance.producer import (
    MaintenanceProducer,
    MaintenanceProducerError,
    MaintenanceProducerRequest,
)
from vnalpha.maintenance.software_identity import resolve_software_identity
from vnalpha.maintenance.source_routing import (
    MaintenanceSourcePolicy,
    RoutedDataProvisioningService,
    resolve_maintenance_source_policy,
)
from vnalpha.observability.context import set_correlation_id
from vnalpha.warehouse.connection import get_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

app = typer.Typer(help="Run deterministic market maintenance operations.")


@app.command("enqueue")
def enqueue(
    date: str = typer.Option("today", "--date", help="Vietnam market date."),
    universe: str = typer.Option("VN30", "--universe"),
    snapshot_id: str | None = typer.Option(None, "--snapshot-id"),
    priority: int = typer.Option(0, "--priority", min=0, max=1000),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Freeze a maintenance scope and detach its bounded queue acquisition work."""
    try:
        result = MaintenanceProducer().produce(
            MaintenanceProducerRequest(
                date=date,
                universe=universe,
                snapshot_id=snapshot_id,
                priority=priority,
            )
        )
    except MaintenanceProducerError as error:
        typer.echo(f"Maintenance enqueue failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    payload = {
        "maintenance_run_id": result.maintenance_run_id,
        "state": result.state.value,
        "resolved_session": result.resolved_session,
        "universe_snapshot_id": result.universe_snapshot_id,
        "expected_count": result.expected_count,
        "submitted_count": result.submitted_count,
        "joined_count": result.joined_count,
        "mapped_count": result.mapped_count,
        "correlation_id": result.correlation_id,
    }
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(
            f"{result.state.value} run={result.maintenance_run_id} "
            f"session={result.resolved_session} expected={result.expected_count} "
            f"submitted={result.submitted_count} joined={result.joined_count} "
            f"mapped={result.mapped_count} correlation_id={result.correlation_id}"
        )


@app.command("daily")
def daily(
    date: str = typer.Option("today", "--date", help="Vietnam market date."),
    symbols: str | None = typer.Option(
        None, "--symbols", help="Comma-separated bounded equity symbols."
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        help=(
            "Legacy OHLCV source applied only to equity and index OHLCV. "
            "It never overrides symbol-reference or membership sources."
        ),
    ),
    reference_source: str | None = typer.Option(
        None,
        "--reference-source",
        help="Explicit source for reference.symbols.",
    ),
    equity_source: str | None = typer.Option(
        None,
        "--equity-source",
        help="Explicit source for equity.ohlcv.",
    ),
    index_source: str | None = typer.Option(
        None,
        "--index-source",
        help="Explicit source for index.ohlcv.",
    ),
    membership_source: str | None = typer.Option(
        None,
        "--membership-source",
        help="Explicit source for index/sector membership snapshots.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run one maintenance invocation with independent dataset source policy."""
    requested_symbols = _parse_symbols(symbols)
    policy = _resolve_maintenance_policy(
        source=source,
        reference_source=reference_source,
        equity_source=equity_source,
        index_source=index_source,
        membership_source=membership_source,
    )
    with _maintenance_connection(ephemeral=dry_run) as conn:
        set_correlation_id()
        started_at = datetime.now(timezone.utc)
        service = DailyMaintenanceService(
            conn,
            provisioning_factory=lambda routed_conn: RoutedDataProvisioningService(
                routed_conn,
                policy,
            ),
        )
        result = service.run(
            DailyMaintenanceRequest(
                date=date,
                symbols=requested_symbols,
                # The routed adapter owns source selection. Passing a single source
                # here would reintroduce the cross-dataset ambiguity fixed by #253.
                source=None,
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
                source_policy=policy.to_dict(),
            )

        payload = result.to_dict()
        payload["source_policy"] = policy.to_dict()
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


def _resolve_maintenance_policy(
    *,
    source: str | None,
    reference_source: str | None,
    equity_source: str | None,
    index_source: str | None,
    membership_source: str | None,
) -> MaintenanceSourcePolicy:
    try:
        return resolve_maintenance_source_policy(
            legacy_ohlcv_source=source,
            reference_source=reference_source,
            equity_source=equity_source,
            index_source=index_source,
            membership_source=membership_source,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _resolve_source_policy(source: str | None) -> dict[str, object]:
    """Resolve the default maintenance source policy as a serializable dict.

    Shared by the maintenance CLI, the persisted ledger and readiness output so
    that every surface resolves the same per-dataset source policy (#253). The
    optional ``source`` applies only to equity/index OHLCV, exactly like the
    ``--source`` legacy flag; it never overrides reference or membership.
    """
    return _resolve_maintenance_policy(
        source=source,
        reference_source=None,
        equity_source=None,
        index_source=None,
        membership_source=None,
    ).to_dict()


@contextmanager
def _maintenance_connection(*, ephemeral: bool) -> Iterator[duckdb.DuckDBPyConnection]:
    if ephemeral:
        with duckdb.connect(":memory:") as connection:
            run_migrations(conn=connection)
            yield connection
        return
    with WarehouseWriteCoordinator().transaction() as connection:
        run_migrations(conn=connection)
        yield connection


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
    """Report per-dataset readiness and the default resolved source policy."""
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
        10,
        "--sessions",
        help="Required consecutive session count.",
    ),
    rerun_dates: int = typer.Option(
        2,
        "--rerun-dates",
        help="Required number of dates with a same-date rerun.",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate persisted ledger evidence for issue #255."""
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
            f"  consecutive_market_sessions: {report['consecutive_market_sessions']}"
        )
        typer.echo(f"  identity_complete: {report['identity_complete']}")
        typer.echo(f"  source_policy_complete: {report['source_policy_complete']}")
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
