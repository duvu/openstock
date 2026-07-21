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

app = typer.Typer(help="Build derived datasets from raw warehouse data.")


@app.command("canonical")
def build_canonical_cmd(
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    interval: str = typer.Option("1D", "--interval"),
):
    """Build canonical OHLCV from raw data."""
    set_correlation_id()
    with command_lifecycle("build canonical"):
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
            result = _execute(
                conn,
                DataProvisioningRequest(
                    "build",
                    "canonical",
                    symbol=symbol,
                    interval=interval,
                    allow_all_symbols=symbol is None,
                ),
            )
        typer.echo(
            f"Canonical build complete: {result.counts['upserted']} rows, "
            f"{result.counts['rejected']} symbols rejected"
        )


@app.command("adjustment-factors")
def build_adjustment_factors_cmd(
    limit: int = typer.Option(100, "--limit", min=1, max=10_000),
) -> None:
    """Derive factors and rebuild unresolved corporate-action ranges."""
    set_correlation_id()
    with command_lifecycle("build adjustment-factors"):
        from vnalpha.corporate_actions.adjusted_prices import (
            rebuild_pending_adjusted_ranges,
        )
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
            results = rebuild_pending_adjusted_ranges(conn, limit=limit)
        typer.echo(
            f"Adjusted ranges rebuilt: {len(results)}; "
            f"rows={sum(item.rows_written for item in results)}"
        )


@app.command("adjusted-ohlcv")
def build_adjusted_ohlcv_cmd(
    symbol: str = typer.Option(..., "--symbol"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
) -> None:
    """Build a bounded backward-adjusted OHLCV derived series."""
    set_correlation_id()
    with command_lifecycle("build adjusted-ohlcv"):
        from vnalpha.corporate_actions.adjusted_prices import build_adjusted_ohlcv
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
            result = build_adjusted_ohlcv(
                conn,
                symbol,
                from_date=from_date,
                to_date=to_date,
            )
        typer.echo(
            f"Adjusted OHLCV built: symbol={result.symbol} "
            f"rows={result.rows_written} factors={result.factors_used} "
            f"version={result.adjustment_version}"
        )


@app.command("features")
def build_features_cmd(
    date: str = typer.Option(
        "today", "--date", help="Reference date (YYYY-MM-DD or 'today')."
    ),
    symbols: Optional[str] = typer.Option(
        None, "--symbols", help="Comma-separated symbols, default: all."
    ),
    benchmark: str | None = typer.Option(
        None,
        "--benchmark",
        help="Benchmark symbol for relative strength; defaults to the benchmark policy.",
    ),
) -> None:
    """Compute technical features for all symbols on the given date."""
    set_correlation_id()
    with command_lifecycle("build features"):
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
            result = _execute(
                conn,
                DataProvisioningRequest(
                    "build",
                    "features",
                    symbols=tuple(symbols.split(",")) if symbols else None,
                    allow_all_symbols=symbols is None,
                    date=date,
                    benchmark=benchmark,
                ),
            )
        typer.echo(
            f"Features built: {result.counts['built']} symbols, "
            f"skipped: {result.counts['skipped']}"
        )


@app.command("market-regime")
def build_market_regime_cmd(
    date: str = typer.Option(..., "--date", help="Exact as-of date (YYYY-MM-DD)."),
) -> None:
    """Build one bounded persisted market-regime snapshot."""
    set_correlation_id()
    with command_lifecycle("build market-regime"):
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
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
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
            result = _execute(
                conn, DataProvisioningRequest("build", "sector-strength", date=date)
            )
        typer.echo(
            f"Sector strength built: {result.counts['sectors']} sectors "
            f"({result.status.value})"
        )


def _execute(conn, request: DataProvisioningRequest) -> DataProvisioningResult:
    try:
        result = DataProvisioningService(conn).execute(request)
    except DataProvisioningValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if result.status is ProvisioningStatus.FAILED:
        typer.echo(result.error or "Data provisioning did not complete.", err=True)
        raise typer.Exit(code=1)
    return result
