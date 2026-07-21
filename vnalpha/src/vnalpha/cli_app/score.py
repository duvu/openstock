from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.dates import resolve_date
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
    resolve_scoring_policy,
)

_POLICY_USAGE = "--scoring-policy must use ID@version."


def score(
    date: str = typer.Option(
        "today", "--date", help="Reference date (YYYY-MM-DD or 'today')."
    ),
    symbols: Optional[str] = typer.Option(
        None, "--symbols", help="Comma-separated symbols to score."
    ),
    top_n: int = typer.Option(30, "--top-n", help="Maximum candidates in watchlist."),
    min_score: float = typer.Option(
        0.40, "--min-score", help="Minimum composite score threshold."
    ),
    scoring_policy: str | None = typer.Option(
        None,
        "--scoring-policy",
        help="Immutable scoring policy ID and version selected by the operator.",
    ),
    rebuild_policy: bool = typer.Option(
        False,
        "--rebuild-policy",
        help="Explicitly replace legacy or different-policy rows in the requested scope.",
    ),
) -> None:
    """Run the shared provisioning path that invokes ``generate_watchlist``."""
    set_correlation_id()
    from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

    with WarehouseWriteCoordinator().transaction() as conn:
        resolved_date = resolve_date(date, conn=conn)
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
            typer.echo(_POLICY_USAGE, err=True)
            raise typer.Exit(code=1) from exc
        try:
            selected_policy = resolve_scoring_policy(
                policy_id,
                policy_version,
                as_of_date=resolved_date,
                conn=conn,
                use_active_default=policy_auto,
            )
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        with command_lifecycle("score"):
            try:
                result = _execute(
                    conn,
                    DataProvisioningRequest(
                        "build",
                        "score",
                        symbols=tuple(symbols.split(",")) if symbols else None,
                        allow_all_symbols=symbols is None,
                        date=resolved_date,
                        top_n=top_n,
                        min_score=min_score,
                        scoring_policy_id=selected_policy.policy_id,
                        scoring_policy_version=selected_policy.version,
                        scoring_policy_auto=policy_auto,
                        rebuild_policy=rebuild_policy,
                    ),
                )
            except Exception as exc:
                typer.echo(f"Score command failed: {exc}", err=True)
                raise typer.Exit(code=1) from exc

            typer.echo(
                f"Scored {result.counts['scored']} symbols — {result.counts['saved']} candidates in watchlist for {result.resolved_date}"
            )
            for warning in result.warnings:
                typer.echo(f"Warning: {warning}", err=True)
            typer.echo(
                "Scoring policy: "
                f"{selected_policy.policy_id}@{selected_policy.version} "
                f"status={selected_policy.lifecycle_status.value} "
                f"hash={selected_policy.payload_hash} "
                f"rebuild={'explicit' if rebuild_policy else 'guarded'}"
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


def register(app: typer.Typer) -> None:
    app.command("score")(score)
