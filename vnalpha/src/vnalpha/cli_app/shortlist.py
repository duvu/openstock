from __future__ import annotations

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def shortlist(
    date: str = typer.Option(
        "today", "--date", help="Reference date (YYYY-MM-DD or 'today')."
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        min=1,
        max=20,
        help="Maximum shortlist rows to display.",
    ),
    min_score: float | None = typer.Option(
        None, "--min-score", help="Minimum raw candidate score for shortlist inclusion."
    ),
) -> None:
    """Run a deterministic research shortlist and print the ranked candidates."""
    set_correlation_id()
    with command_lifecycle("shortlist"):
        from vnalpha.tools.research_intelligence import generate_shortlist
        from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator

        with WarehouseWriteCoordinator().transaction() as conn:
            result = generate_shortlist(conn, date=date, top=limit, min_score=min_score)
        data = result.data if isinstance(result.data, dict) else {}
        candidates = data.get("shortlist") if isinstance(data, dict) else []
        if not isinstance(candidates, list):
            candidates = []
        shortlist_date = data.get("as_of_date") if isinstance(data, dict) else None
        header_date = shortlist_date or date or "today"

        try:
            from rich.console import Console
            from rich.table import Table

            table = Table(title=f"Research Shortlist — {header_date}")
            table.add_column("#", width=4, justify="right")
            table.add_column("Symbol", style="bold cyan", width=8)
            table.add_column("Shortlist Score", justify="right", width=14)
            table.add_column("Candidate Score", justify="right", width=15)
            table.add_column("Setup", width=18)
            table.add_column("Sector", width=18)
            table.add_column("Why shortlisted", width=40)

            if not candidates:
                typer.echo(
                    f"No shortlist candidates available for {header_date}. "
                    f"Reason: {result.summary or 'No shortlist output.'}"
                )
                return

            for row in candidates:
                why = ", ".join(row.get("why_shortlisted", []))
                table.add_row(
                    str(row.get("rank", "")),
                    str(row.get("symbol", "")),
                    f"{float(row.get('shortlist_score') or 0.0):.3f}",
                    f"{float(row.get('candidate_score') or 0.0):.3f}",
                    str(row.get("setup_type") or "UNCLASSIFIED"),
                    str(row.get("sector") or "UNCLASSIFIED"),
                    why,
                )
            console = Console()
            console.print(table)
            run_id = data.get("shortlist_run_id") if isinstance(data, dict) else None
            if run_id:
                typer.echo(f"Shortlist run: {run_id}")
            return
        except ImportError:
            if not candidates:
                typer.echo(
                    f"No shortlist candidates available for {header_date}. "
                    f"Reason: {result.summary or 'No shortlist output.'}"
                )
                return
            for row in candidates:
                typer.echo(
                    f"{row.get('rank', '')}: {row.get('symbol')} "
                    f"shortlist={float(row.get('shortlist_score') or 0.0):.3f} "
                    f"candidate={float(row.get('candidate_score') or 0.0):.3f}"
                )


def register(app: typer.Typer) -> None:
    app.command("shortlist")(shortlist)
