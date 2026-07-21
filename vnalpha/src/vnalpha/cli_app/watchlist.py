from __future__ import annotations

import typer

from vnalpha.core.dates import resolve_date
from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def watchlist(
    date: str = typer.Option(
        "today", "--date", help="Reference date (YYYY-MM-DD or 'today')."
    ),
) -> None:
    """Show the daily research watchlist for the given date as a Rich table."""
    set_correlation_id()
    with command_lifecycle("watchlist"):
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.repositories import get_watchlist as _get_watchlist

        with get_connection() as conn:
            target_date = resolve_date(date, conn=conn)
            rows = _get_watchlist(conn, target_date)

        if not rows:
            typer.echo(
                f"No watchlist entries for {target_date}. Run 'vnalpha score --date {target_date}' first."
            )
            return

        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(
                title=f"Research Candidates — {target_date}", show_lines=False
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Symbol", style="bold cyan", width=8)
            table.add_column("Score", justify="right", width=7)
            table.add_column("Class", width=18)
            table.add_column("Setup", width=22)
            table.add_column("Risk Flags", width=30)
            table.add_column("Policy", width=28)
            table.add_column("Lifecycle", width=14)

            import json as _json

            for row in rows:
                flags = _json.loads(row.get("risk_flags_json") or "[]")
                table.add_row(
                    str(row["rank"]),
                    row["symbol"],
                    f"{row['score']:.3f}",
                    row.get("candidate_class", ""),
                    row.get("setup_type", ""),
                    ", ".join(flags) if flags else "—",
                    (
                        f"{row.get('scoring_policy_id') or 'UNKNOWN'}@"
                        f"{row.get('scoring_policy_version') or 'UNKNOWN'}"
                    ),
                    row.get("scoring_policy_status") or "UNKNOWN",
                )
            console.print(table)
            console.print(
                "[dim]Policy hash: "
                f"{rows[0].get('scoring_policy_hash') or 'UNKNOWN'}[/dim]"
            )
            console.print(
                f"[dim]Score range: 0.0–1.0 | For evidence details run: vnalpha tui --date {target_date}[/dim]"
            )
        except ImportError:
            typer.echo(f"{'#':<4} {'Symbol':<8} {'Score':>7}  {'Class':<18}  {'Setup'}")
            typer.echo("-" * 65)
            for row in rows:
                typer.echo(
                    f"{row['rank']:<4} {row['symbol']:<8} {row['score']:>7.3f}  {row.get('candidate_class', ''):<18}  {row.get('setup_type', '')}"
                )
            typer.echo(
                f"Score range: 0.0-1.0 | For evidence: vnalpha tui --date {target_date}"
            )
            typer.echo(
                "Policy: "
                f"{rows[0].get('scoring_policy_id') or 'UNKNOWN'}@"
                f"{rows[0].get('scoring_policy_version') or 'UNKNOWN'} "
                f"status={rows[0].get('scoring_policy_status') or 'UNKNOWN'} "
                f"hash={rows[0].get('scoring_policy_hash') or 'UNKNOWN'}"
            )


def register(app: typer.Typer) -> None:
    app.command("watchlist")(watchlist)
