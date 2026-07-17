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
from vnalpha.scoring.policy import resolve_scoring_policy


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
    scoring_policy: str = typer.Option(
        "openstock-candidate-score@v1.0",
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
    with command_lifecycle("score"):
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        try:
            policy_id, policy_version = scoring_policy.rsplit("@", 1)
        except ValueError as exc:
            typer.echo("--scoring-policy must use ID@version", err=True)
            raise typer.Exit(code=1) from exc
        try:
            selected_policy = resolve_scoring_policy(policy_id, policy_version)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        result = _execute(
            conn,
            DataProvisioningRequest(
                "build",
                "score",
                symbols=tuple(symbols.split(",")) if symbols else None,
                allow_all_symbols=symbols is None,
                date=date,
                top_n=top_n,
                min_score=min_score,
                scoring_policy_id=policy_id,
                scoring_policy_version=policy_version,
                rebuild_policy=rebuild_policy,
            ),
        )
        typer.echo(
            f"Scored {result.counts['scored']} symbols — {result.counts['saved']} candidates in watchlist for {result.resolved_date}"
        )
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
