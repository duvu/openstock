from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def outcome_evaluate(
    date: Optional[str] = typer.Option(
        None, "--date", help="Evaluate a single watchlist date"
    ),
    from_date: Optional[str] = typer.Option(
        None, "--from", help="Start date for range evaluation"
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to", help="End date for range evaluation"
    ),
):
    """Evaluate candidate outcomes for a date or date range."""
    set_correlation_id()
    with command_lifecycle("outcome evaluate"):
        from vnalpha.core.dates import resolve_date
        from vnalpha.outcomes.evaluator import (
            evaluate_date_range,
            evaluate_watchlist_date,
        )
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)

        if date:
            target = resolve_date(date)
            result = evaluate_watchlist_date(conn, target)
            typer.echo(
                f"Evaluated {result['evaluated']} candidate-horizon pairs for {target}."
            )
            typer.echo(f"Persisted: {result['persisted']}, Errors: {result['errors']}")
            if result.get("evaluation_run_id"):
                typer.echo(f"Evaluation run: {result['evaluation_run_id']}")
            if result.get("aggregates"):
                typer.echo(f"Aggregates: {len(result['aggregates'])} horizons")
        elif from_date and to_date:
            results = evaluate_date_range(conn, from_date, to_date)
            total = sum(r["evaluated"] for r in results)
            persisted = sum(r["persisted"] for r in results)
            aggregate_horizons = sum(len(r.get("aggregates", {})) for r in results)
            typer.echo(
                f"Evaluated {len(results)} dates, {total} pairs, {persisted} persisted, "
                f"{aggregate_horizons} aggregate horizons."
            )
            for r in results:
                run_id = r.get("evaluation_run_id") or "none"
                typer.echo(
                    f"  {r['watchlist_date']}: run_id={run_id}, evaluated={r['evaluated']}, errors={r['errors']}"
                )
        else:
            typer.echo("Provide --date or --from/--to.", err=True)
            raise typer.Exit(code=1)
        conn.close()
