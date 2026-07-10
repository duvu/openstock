import typer

from vnalpha.cli_app import (
    outcome_evaluate,
    outcome_performance,
    outcome_report,
    outcome_summary,
)

app = typer.Typer(name="outcome", help="Outcome tracking commands.")
app.command("evaluate")(outcome_evaluate.outcome_evaluate)
app.command("candidates")(outcome_summary.outcome_candidates)
app.command("watchlist")(outcome_summary.outcome_watchlist)
app.command("buckets")(outcome_performance.outcome_buckets)
app.command("setups")(outcome_performance.outcome_setups)
app.command("risks")(outcome_performance.outcome_risks)
app.command("report")(outcome_report.outcome_report)
