import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def outcome_buckets(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show score bucket performance."""
    set_correlation_id()
    with command_lifecycle("outcome buckets"):
        from rich.console import Console
        from rich.table import Table

        from vnalpha.outcomes.repositories import list_score_bucket_performance
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        rows = list_score_bucket_performance(conn, horizon)
        conn.close()
        console = Console()
        if not rows:
            console.print(f"[dim]No score bucket data for horizon={horizon}[/dim]")
            return
        table = Table(title=f"Score Bucket Performance — Horizon {horizon} sessions")
        table.add_column("Bucket")
        table.add_column("Count")
        table.add_column("Avg Fwd Rtn")
        table.add_column("Hit Rate")
        table.add_column("Failure Rate")
        table.add_column("Basis")
        table.add_column("Policy")
        for row in rows:
            fwd = (
                f"{row['avg_forward_return']:.2%}"
                if row["avg_forward_return"] is not None
                else "—"
            )
            hit = f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
            fail = (
                f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "—"
            )
            table.add_row(
                row["score_bucket"],
                str(row["candidate_count"] or 0),
                fwd,
                hit,
                fail,
                row.get("price_basis") or "UNKNOWN",
                row.get("scoring_policy_version") or "UNKNOWN",
            )
        console.print(table)


def outcome_setups(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show setup type performance."""
    set_correlation_id()
    with command_lifecycle("outcome setups"):
        from rich.console import Console
        from rich.table import Table

        from vnalpha.outcomes.repositories import list_setup_type_performance
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        rows = list_setup_type_performance(conn, horizon)
        conn.close()
        console = Console()
        if not rows:
            console.print(f"[dim]No setup type data for horizon={horizon}[/dim]")
            return
        table = Table(title=f"Setup Type Performance — Horizon {horizon} sessions")
        table.add_column("Setup Type")
        table.add_column("Count")
        table.add_column("Avg Fwd Rtn")
        table.add_column("Hit Rate")
        table.add_column("Failure Rate")
        table.add_column("Basis")
        table.add_column("Policy")
        for row in rows:
            fwd = (
                f"{row['avg_forward_return']:.2%}"
                if row["avg_forward_return"] is not None
                else "—"
            )
            hit = f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
            fail = (
                f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "—"
            )
            table.add_row(
                row["setup_type"],
                str(row["candidate_count"] or 0),
                fwd,
                hit,
                fail,
                row.get("price_basis") or "UNKNOWN",
                row.get("scoring_policy_version") or "UNKNOWN",
            )
        console.print(table)


def outcome_risks(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show risk flag performance."""
    set_correlation_id()
    with command_lifecycle("outcome risks"):
        from rich.console import Console
        from rich.table import Table

        from vnalpha.outcomes.repositories import list_risk_flag_performance
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        conn = get_connection()
        run_migrations(conn=conn)
        rows = list_risk_flag_performance(conn, horizon)
        conn.close()
        console = Console()
        if not rows:
            console.print(f"[dim]No risk flag data for horizon={horizon}[/dim]")
            return
        table = Table(title=f"Risk Flag Performance — Horizon {horizon} sessions")
        table.add_column("Risk Flag")
        table.add_column("Count")
        table.add_column("Avg Fwd Rtn")
        table.add_column("Hit Rate")
        table.add_column("Failure Rate")
        table.add_column("Basis")
        table.add_column("Policy")
        for row in rows:
            fwd = (
                f"{row['avg_forward_return']:.2%}"
                if row["avg_forward_return"] is not None
                else "—"
            )
            hit = f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
            fail = (
                f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "—"
            )
            table.add_row(
                row["risk_flag"],
                str(row["candidate_count"] or 0),
                fwd,
                hit,
                fail,
                row.get("price_basis") or "UNKNOWN",
                row.get("scoring_policy_version") or "UNKNOWN",
            )
        console.print(table)
