from __future__ import annotations

import json

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
from vnalpha.scoring.policy import (
    BASELINE_SCORING_POLICY,
    parse_scoring_policy_reference,
)

app = typer.Typer(help="Explicit bounded data downloads and derived-data builds.")
download_app = typer.Typer(help="Download approved raw market data.")
build_app = typer.Typer(help="Build approved deterministic research artifacts.")
sync_app = typer.Typer(help="Run bounded incremental market-data maintenance.")
repair_app = typer.Typer(help="Repair bounded canonical OHLCV gaps.")
status_app = typer.Typer(help="Inspect bounded data-ingestion status.")
app.add_typer(download_app, name="download")
app.add_typer(build_app, name="build")
app.add_typer(sync_app, name="sync")
app.add_typer(repair_app, name="repair")
app.add_typer(status_app, name="status")


@download_app.command("symbols")
def download_symbols(
    source: str | None = typer.Option(None, "--source", help="Preferred provider."),
) -> None:
    _run(
        DataProvisioningRequest(operation="download", artifact="symbols", source=source)
    )


@download_app.command("ohlcv")
def download_ohlcv(
    symbol: str = typer.Argument(..., help="Equity symbol."),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)."),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)."),
    source: str | None = typer.Option(None, "--source", help="Preferred provider."),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="download",
            artifact="ohlcv",
            symbol=symbol,
            start=start,
            end=end,
            source=source,
        )
    )


@download_app.command("index")
def download_index(
    symbol: str | None = typer.Argument(
        None, help="Index symbol; defaults to VNINDEX."
    ),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)."),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)."),
    source: str | None = typer.Option(None, "--source", help="Preferred provider."),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="download",
            artifact="index",
            symbol=symbol,
            start=start,
            end=end,
            source=source,
        )
    )


@download_app.command("corporate-actions")
def download_corporate_actions(
    symbol: str = typer.Argument(..., help="Equity symbol."),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)."),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)."),
    source: str | None = typer.Option(None, "--source", help="Preferred provider."),
) -> None:
    _run_corporate_actions(symbol=symbol, start=start, end=end, source=source)


@status_app.command("fundamentals")
def status_fundamentals(
    symbol: str = typer.Argument(..., help="Equity symbol."),
    as_of: str = typer.Option(..., "--as-of", help="As-of date (YYYY-MM-DD)."),
    scope: str = typer.Option(
        "CONSOLIDATED", "--scope", help="CONSOLIDATED or SEPARATE."
    ),
) -> None:
    """Read the publication-aware fundamentals snapshot (issue #257).

    Only facts published on or before ``--as-of`` are returned, so future
    publications never leak into a historical read.
    """
    from dataclasses import asdict

    from vnalpha.fundamentals import StatementScope, as_of_snapshot
    from vnalpha.warehouse.connection import get_connection

    try:
        statement_scope = StatementScope(scope.upper())
    except ValueError as exc:
        raise typer.BadParameter("scope must be CONSOLIDATED or SEPARATE") from exc

    with get_connection() as conn:
        snapshot = as_of_snapshot(
            conn, symbol.upper(), as_of, statement_scope=statement_scope
        )
    typer.echo(
        json.dumps(
            {
                "symbol": symbol.upper(),
                "as_of": as_of,
                "facts": [asdict(f) for f in snapshot],
            },
            sort_keys=True,
        )
    )


@status_app.command("corporate-actions")
def status_corporate_actions(
    symbol: str | None = typer.Argument(None, help="Optional equity symbol."),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)."),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)."),
) -> None:
    from vnalpha.ingestion.corporate_actions import corporate_action_status
    from vnalpha.warehouse.connection import get_connection

    with get_connection() as conn:
        typer.echo(
            json.dumps(
                corporate_action_status(conn, symbol=symbol, start=start, end=end),
                sort_keys=True,
            )
        )


@build_app.command("canonical")
def build_canonical(
    symbol: str = typer.Argument(..., help="Symbol to canonicalize."),
) -> None:
    _run(
        DataProvisioningRequest(operation="build", artifact="canonical", symbol=symbol)
    )


@build_app.command("features")
def build_features(
    symbol: str = typer.Argument(..., help="Symbol to build."),
    date: str = typer.Option(..., "--date", help="As-of date (YYYY-MM-DD)."),
    benchmark: str | None = typer.Option(
        None, "--benchmark", help="Benchmark symbol for relative strength."
    ),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="build",
            artifact="features",
            symbol=symbol,
            date=date,
            benchmark=benchmark,
        )
    )


@build_app.command("score")
def build_score(
    symbol: str = typer.Argument(..., help="Symbol to score."),
    date: str = typer.Option(..., "--date", help="As-of date (YYYY-MM-DD)."),
    scoring_policy: str | None = typer.Option(
        None,
        "--scoring-policy",
        help="Immutable scoring policy ID and version.",
    ),
    rebuild_policy: bool = typer.Option(False, "--rebuild-policy"),
) -> None:
    policy_auto = scoring_policy is None
    try:
        policy_id, policy_version = (
            parse_scoring_policy_reference(scoring_policy)
            if scoring_policy is not None
            else (
                BASELINE_SCORING_POLICY.policy_id,
                BASELINE_SCORING_POLICY.version,
            )
        )
    except ValueError as exc:
        raise typer.BadParameter(
            "Use ID@version.", param_hint="--scoring-policy"
        ) from exc
    _run(
        DataProvisioningRequest(
            operation="build",
            artifact="score",
            symbol=symbol,
            date=date,
            scoring_policy_id=policy_id,
            scoring_policy_version=policy_version,
            scoring_policy_auto=policy_auto,
            rebuild_policy=rebuild_policy,
        )
    )


@build_app.command("market-regime")
def build_market_regime(
    date: str = typer.Option(..., "--date", help="As-of date (YYYY-MM-DD)."),
) -> None:
    _run(
        DataProvisioningRequest(operation="build", artifact="market-regime", date=date)
    )


@build_app.command("sector-strength")
def build_sector_strength(
    date: str = typer.Option(..., "--date", help="As-of date (YYYY-MM-DD)."),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="build", artifact="sector-strength", date=date
        )
    )


@sync_app.command("daily")
def sync_daily(
    date: str | None = typer.Option(None, "--date", help="Market date (YYYY-MM-DD)."),
    source: str | None = typer.Option(None, "--source", help="Preferred provider."),
    interval: str = typer.Option("1D", "--interval", help="OHLCV interval."),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="sync",
            artifact="daily",
            date=date,
            source=source,
            interval=interval,
        )
    )


@app.command("gaps")
def gaps(
    symbol: str = typer.Argument(..., help="Equity symbol."),
    from_date: str | None = typer.Option(
        None, "--from", help="Start date (YYYY-MM-DD)."
    ),
    to_date: str | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)."),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="gaps",
            artifact="ohlcv",
            symbol=symbol,
            start=from_date,
            end=to_date,
        )
    )


@repair_app.command("ohlcv")
def repair_ohlcv(
    symbol: str = typer.Argument(..., help="Equity symbol."),
    from_date: str | None = typer.Option(
        None, "--from", help="Start date (YYYY-MM-DD)."
    ),
    to_date: str | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)."),
    source: str | None = typer.Option(None, "--source", help="Preferred provider."),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="repair",
            artifact="ohlcv",
            symbol=symbol,
            start=from_date,
            end=to_date,
            source=source,
        )
    )


def _run_corporate_actions(
    *, symbol: str, start: str | None, end: str | None, source: str | None
) -> None:
    from vnalpha.ingestion.corporate_actions import sync_corporate_actions
    from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise typer.BadParameter("symbol must not be empty")
    set_correlation_id()
    with command_lifecycle("data download corporate-actions"):
        with WarehouseWriteCoordinator().transaction() as conn:
            result = sync_corporate_actions(
                conn,
                symbol=normalized_symbol,
                start=start,
                end=end,
                source=source,
            )
        typer.echo(json.dumps(result, sort_keys=True))
        if result["status"] in {"FAILED", "UNSUPPORTED"}:
            raise typer.Exit(code=1)


def _run(request: DataProvisioningRequest) -> None:
    set_correlation_id()
    command = f"data {request.operation} {request.artifact}"
    with command_lifecycle(command):
        try:
            DataProvisioningService.validate_request(request)
        except DataProvisioningValidationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
            try:
                result = DataProvisioningService(conn).execute(request)
            except DataProvisioningValidationError as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(code=1) from exc
        typer.echo(_render(result))
        if result.status is ProvisioningStatus.FAILED:
            raise typer.Exit(code=1)


def _render(result: DataProvisioningResult) -> str:
    return json.dumps(
        {
            "status": result.status.value,
            "operation": result.operation,
            "artifact": result.artifact,
            "symbol": result.symbol,
            "source": result.source,
            "start": result.start,
            "end": result.end,
            "resolved_date": result.resolved_date,
            "requested_date": result.requested_date,
            "freshness": result.freshness,
            "lineage": result.lineage,
            "follow_up": result.follow_up,
            "counts": result.counts,
            "warnings": list(result.warnings),
            "error": result.error,
            "terminal_reason": result.terminal_reason,
            "correlation_id": result.correlation_id,
            "symbol_results": [
                symbol_result.to_payload() for symbol_result in result.symbol_results
            ],
        },
        sort_keys=True,
    )
