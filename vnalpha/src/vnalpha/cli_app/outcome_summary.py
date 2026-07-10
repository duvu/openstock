import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def outcome_candidates(
    date: str = typer.Option(..., "--date", help="Watchlist date"),
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show candidate outcomes for a date and horizon."""
    set_correlation_id()
    with command_lifecycle("outcome candidates"):
        from rich.console import Console
        from rich.table import Table

        from vnalpha.core.dates import resolve_date
        from vnalpha.outcomes.repositories import get_candidate_outcomes
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        rows = get_candidate_outcomes(conn, resolve_date(date), horizon)
        conn.close()

        console = Console()
        if not rows:
            console.print(
                f"[dim]No candidate outcomes for {date} horizon={horizon}[/dim]"
            )
            return

        table = Table(title=f"Candidate Outcomes — {date} | Horizon {horizon} sessions")
        table.add_column("Symbol")
        table.add_column("Status")
        table.add_column("Score")
        table.add_column("Forward Rtn")
        table.add_column("Excess Rtn")
        table.add_column("Hit")
        table.add_column("Failure")

        for row in rows:
            fwd = (
                f"{row['forward_return']:.2%}"
                if row["forward_return"] is not None
                else "—"
            )
            exc = (
                f"{row['excess_return_vs_vnindex']:.2%}"
                if row["excess_return_vs_vnindex"] is not None
                else "—"
            )
            score = f"{row['score']:.2f}" if row["score"] is not None else "—"
            table.add_row(
                row["symbol"],
                row["outcome_status"],
                score,
                fwd,
                exc,
                str(row["hit"]) if row["hit"] is not None else "—",
                str(row["failure"]) if row["failure"] is not None else "—",
            )
        console.print(table)


def outcome_watchlist(
    date: str = typer.Option(..., "--date", help="Watchlist date"),
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show watchlist outcome summary for a date and horizon."""
    set_correlation_id()
    with command_lifecycle("outcome watchlist"):
        from rich.console import Console
        from rich.panel import Panel

        from vnalpha.core.dates import resolve_date
        from vnalpha.outcomes.repositories import get_watchlist_outcome
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        result = get_watchlist_outcome(conn, resolve_date(date), horizon)
        conn.close()

        console = Console()
        if result is None:
            console.print(
                f"[dim]No watchlist outcome for {date} horizon={horizon}[/dim]"
            )
            return

        avg_fwd = (
            f"{result['avg_forward_return']:.2%}"
            if result["avg_forward_return"] is not None
            else "—"
        )
        avg_exc = (
            f"{result['avg_excess_return']:.2%}"
            if result["avg_excess_return"] is not None
            else "—"
        )
        hit_rate = (
            f"{result['hit_rate']:.1%}" if result["hit_rate"] is not None else "—"
        )
        fail_rate = (
            f"{result['failure_rate']:.1%}"
            if result["failure_rate"] is not None
            else "—"
        )
        lines = [
            f"Candidates: {result.get('candidate_count')}",
            f"Complete: {result.get('complete_count')} | Pending: {result.get('pending_count')} | Missing: {result.get('missing_data_count')}",
            f"Avg Forward Return: {avg_fwd}",
            f"Avg Excess Return: {avg_exc}",
            f"Hit Rate: {hit_rate}",
            f"Failure Rate: {fail_rate}",
        ]
        console.print(
            Panel(
                "\n".join(lines),
                title=f"Watchlist Outcome — {date} | Horizon {horizon} sessions",
            )
        )
