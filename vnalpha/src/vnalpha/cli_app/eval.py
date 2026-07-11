"""Commands for deterministic offline evaluation fixtures."""

from __future__ import annotations

import typer

from vnalpha.evals.report import render_report
from vnalpha.evals.runner import run_golden_corpus

app = typer.Typer(name="eval", help="Deterministic offline evaluation commands.")


@app.command("research-answers")
def research_answers(ci: bool = typer.Option(False, "--ci")) -> None:
    """Evaluate the fixed local golden corpus and render stable diagnostics."""

    report = run_golden_corpus()
    for line in render_report(report):
        typer.echo(line)
    if ci and not report.passed:
        raise typer.Exit(1)
