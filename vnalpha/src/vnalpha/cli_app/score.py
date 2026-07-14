from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningService,
    ProvisioningStatus,
)
from vnalpha.observability.commands import command_lifecycle


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
) -> None:
    """Score candidate research setups for the given date and generate the watchlist."""
    set_correlation_id()
    with command_lifecycle("score"):
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        result = DataProvisioningService(conn).execute(
            DataProvisioningRequest(
                "build",
                "score",
                symbols=tuple(symbols.split(",")) if symbols else None,
                allow_all_symbols=symbols is None,
                date=date,
                top_n=top_n,
                min_score=min_score,
            )
        )
        if result.status is ProvisioningStatus.FAILED:
            typer.echo(result.error or "Data provisioning did not complete.", err=True)
            raise typer.Exit(code=1)
        typer.echo(
            f"Scored {result.counts['scored']} symbols — {result.counts['saved']} candidates in watchlist for {result.resolved_date}"
        )


def register(app: typer.Typer) -> None:
    app.command("score")(score)
