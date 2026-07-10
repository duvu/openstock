from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.dates import resolve_date
from vnalpha.core.logging import set_correlation_id
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
        from vnalpha.scoring.generate_watchlist import generate_watchlist
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        target_date = resolve_date(date, conn=conn)
        universe = symbols.split(",") if symbols else None

        result = generate_watchlist(
            conn,
            date=target_date,
            universe=universe,
            top_n=top_n,
            min_score=min_score,
        )
        typer.echo(
            f"Scored {result['scored']} symbols — {result['saved']} candidates in watchlist for {target_date}"
        )


def register(app: typer.Typer) -> None:
    app.command("score")(score)
