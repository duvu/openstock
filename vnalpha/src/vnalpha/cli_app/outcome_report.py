from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def outcome_report(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
    date: Optional[str] = typer.Option(
        None, "--date", help="As-of date (default: latest)"
    ),
):
    """Generate calibration report."""
    set_correlation_id()
    with command_lifecycle("outcome report"):
        from rich.console import Console
        from rich.panel import Panel

        from vnalpha.core.dates import resolve_date
        from vnalpha.outcomes.calibration import generate_calibration_report
        from vnalpha.warehouse.connection import get_connection

        with get_connection() as conn:
            as_of = resolve_date(date) if date else None
            report = generate_calibration_report(conn, horizon, as_of_date=as_of)
        console = Console()
        console.print(
            Panel(
                f"As-of date: {report['as_of_date']} | Horizon: {horizon} sessions\n"
                f"Pending: {report['pending_count']} | Missing: {report['missing_count']}\n"
                f"Score buckets: {len(report.get('score_buckets', []))} | "
                f"Setups: {len(report.get('setup_types', []))} | "
                f"Risk flags: {len(report.get('risk_flags', []))}\n"
                f"Score bucket monotone: {report['score_bucket_monotone']}\n"
                f"Best setup: {report.get('best_setup') or '—'} | Worst setup: {report.get('worst_setup') or '—'}\n"
                f"Worst risk flag: {report.get('worst_risk_flag') or '—'}\n\n"
                f"[dim]{report['interpretation_note']}[/dim]",
                title="Calibration Report",
            )
        )
