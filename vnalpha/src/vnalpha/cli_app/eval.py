"""Commands for deterministic offline evaluation fixtures."""

from __future__ import annotations

import typer

from vnalpha.evals.report import render_report
from vnalpha.evals.runner import run_golden_corpus
from vnalpha.evals.runtime_report import render_runtime_report, runtime_report_json
from vnalpha.evals.runtime_runner import run_runtime_replay_corpus
from vnalpha.evals.symbol_memory_runtime import run_symbol_memory_runtime_corpus

app = typer.Typer(name="eval", help="Deterministic offline evaluation commands.")


@app.command("research-answers")
def research_answers(ci: bool = typer.Option(False, "--ci")) -> None:
    """Evaluate the fixed local golden corpus and render stable diagnostics."""

    report = run_golden_corpus()
    for line in render_report(report):
        typer.echo(line)
    if ci and not report.passed:
        raise typer.Exit(1)


@app.command("research-runtime")
def research_runtime(
    ci: bool = typer.Option(False, "--ci"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    report = run_runtime_replay_corpus()
    if output_json:
        typer.echo(runtime_report_json(report))
    else:
        for line in render_runtime_report(report):
            typer.echo(line)
    if ci and not report.passed:
        raise typer.Exit(1)


@app.command("symbol-memory-runtime")
def symbol_memory_runtime(ci: bool = typer.Option(False, "--ci")) -> None:
    report = run_symbol_memory_runtime_corpus()
    for case in report.cases:
        typer.echo(f"{case.case_id}: {'PASS' if case.passed else 'FAIL'}")
    if ci and not report.passed:
        raise typer.Exit(1)
