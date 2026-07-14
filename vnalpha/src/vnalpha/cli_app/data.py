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

app = typer.Typer(help="Explicit bounded data downloads and derived-data builds.")
download_app = typer.Typer(help="Download approved raw market data.")
build_app = typer.Typer(help="Build approved deterministic research artifacts.")
app.add_typer(download_app, name="download")
app.add_typer(build_app, name="build")


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
) -> None:
    _run(
        DataProvisioningRequest(
            operation="build", artifact="features", symbol=symbol, date=date
        )
    )


@build_app.command("score")
def build_score(
    symbol: str = typer.Argument(..., help="Symbol to score."),
    date: str = typer.Option(..., "--date", help="As-of date (YYYY-MM-DD)."),
) -> None:
    _run(
        DataProvisioningRequest(
            operation="build", artifact="score", symbol=symbol, date=date
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


def _run(request: DataProvisioningRequest) -> None:
    set_correlation_id()
    command = f"data {request.operation} {request.artifact}"
    with command_lifecycle(command):
        try:
            DataProvisioningService.validate_request(request)
        except DataProvisioningValidationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
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
