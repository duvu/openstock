"""vnalpha CLI entry point."""

from __future__ import annotations

from typing import Optional

import typer

from vnalpha.core.dates import resolve_date

app = typer.Typer(name="vnalpha", help="Alpha discovery research CLI.")

# ---------------------------------------------------------------------------
# sync sub-app
# ---------------------------------------------------------------------------
sync_app = typer.Typer(help="Sync data from vnstock-service into the warehouse.")
app.add_typer(sync_app, name="sync")


@sync_app.command("symbols")
def sync_symbols_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Preferred provider"),
):
    """Sync symbol master from vnstock-service."""
    from vnalpha.ingestion.sync_symbols import sync_symbols
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations

    conn = get_connection()
    run_migrations(conn=conn)
    result = sync_symbols(conn, source=source)
    typer.echo(f"Synced {result['synced']} symbols (errors: {result['errors']})")


@sync_app.command("ohlcv")
def sync_ohlcv_cmd(
    symbols: Optional[str] = typer.Option(
        None,
        "--symbols",
        help="Comma-separated symbols (takes precedence over --universe)",
    ),
    universe: Optional[str] = typer.Option(
        None, "--universe", help="Named universe (e.g. VN30). Resolved to symbol list."
    ),
    start: Optional[str] = typer.Option(None, "--start"),
    end: Optional[str] = typer.Option(None, "--end"),
    interval: str = typer.Option("1D", "--interval"),
    source: Optional[str] = typer.Option(None, "--source"),
):
    """Sync equity OHLCV data from vnstock-service.

    Resolution order: --symbols > --universe > all active symbols.
    """
    from vnalpha.core.universe import parse_symbols_or_universe
    from vnalpha.ingestion.sync_ohlcv import sync_ohlcv
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations

    conn = get_connection()
    run_migrations(conn=conn)
    try:
        resolved = parse_symbols_or_universe(symbols, universe)
    except ValueError as err:
        typer.echo(f"Error: {err}", err=True)
        raise typer.Exit(code=1) from err

    result = sync_ohlcv(
        conn, universe=resolved, start=start, end=end, interval=interval, source=source
    )
    typer.echo(
        f"OHLCV sync complete: {result['inserted']} inserted, {result['skipped']} skipped"
    )


@sync_app.command("index")
def sync_index_cmd(
    symbol: str = typer.Option(
        "VNINDEX", "--symbol", help="Index symbol (e.g. VNINDEX)"
    ),
    start: Optional[str] = typer.Option(None, "--start"),
    end: Optional[str] = typer.Option(None, "--end"),
    interval: str = typer.Option("1D", "--interval"),
    source: Optional[str] = typer.Option(None, "--source"),
):
    """Sync index/benchmark OHLCV data from vnstock-service.

    Example: vnalpha sync index --symbol VNINDEX --start 2024-01-01
    """
    from vnalpha.ingestion.sync_index import sync_index_ohlcv
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations

    conn = get_connection()
    run_migrations(conn=conn)
    result = sync_index_ohlcv(
        conn, symbol=symbol, start=start, end=end, interval=interval, source=source
    )
    typer.echo(
        f"Index sync complete ({symbol}): {result['inserted']} inserted, {result['skipped']} skipped"
    )


# ---------------------------------------------------------------------------
# build sub-app
# ---------------------------------------------------------------------------
build_app = typer.Typer(help="Build derived datasets from raw warehouse data.")
app.add_typer(build_app, name="build")


@build_app.command("canonical")
def build_canonical_cmd(
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    interval: str = typer.Option("1D", "--interval"),
):
    """Build canonical OHLCV from raw data."""
    from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
    from vnalpha.warehouse.connection import get_connection

    conn = get_connection()
    result = build_canonical_ohlcv(conn, symbol=symbol, interval=interval)
    typer.echo(
        f"Canonical build complete: {result['upserted']} rows, {result.get('rejected', 0)} symbols rejected"
    )


@build_app.command("features")
def build_features_cmd(
    date: str = typer.Option(
        "today", "--date", help="Reference date (YYYY-MM-DD or 'today')."
    ),
    symbols: Optional[str] = typer.Option(
        None, "--symbols", help="Comma-separated symbols, default: all."
    ),
    benchmark: str = typer.Option(
        "VNINDEX", "--benchmark", help="Benchmark symbol for relative strength."
    ),
) -> None:
    """Compute technical features for all symbols on the given date."""
    from vnalpha.features.build_features import build_features
    from vnalpha.warehouse.connection import get_connection

    target_date = resolve_date(date)
    universe = symbols.split(",") if symbols else None

    conn = get_connection()
    result = build_features(
        conn, target_date=target_date, universe=universe, benchmark_symbol=benchmark
    )
    typer.echo(
        f"Features built: {result['built']} symbols, skipped: {result['skipped']}"
    )


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------


@app.command("init")
def init() -> None:
    """Initialize the local DuckDB warehouse."""
    typer.echo("Initializing warehouse...")
    from vnalpha.warehouse import migrations

    migrations.run_migrations()
    typer.echo("Warehouse ready.")


@app.command("score")
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
    from vnalpha.scoring.generate_watchlist import generate_watchlist
    from vnalpha.warehouse.connection import get_connection

    target_date = resolve_date(date)
    universe = symbols.split(",") if symbols else None

    conn = get_connection()
    result = generate_watchlist(
        conn, date=target_date, universe=universe, top_n=top_n, min_score=min_score
    )
    typer.echo(
        f"Scored {result['scored']} symbols — {result['saved']} candidates in watchlist for {target_date}"
    )


@app.command("watchlist")
def watchlist(
    date: str = typer.Option(
        "today", "--date", help="Reference date (YYYY-MM-DD or 'today')."
    ),
) -> None:
    """Show the daily research watchlist for the given date as a Rich table."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.repositories import get_watchlist as _get_watchlist

    target_date = resolve_date(date)
    conn = get_connection()
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
        table = Table(title=f"Research Candidates — {target_date}", show_lines=False)
        table.add_column("#", style="dim", width=4)
        table.add_column("Symbol", style="bold cyan", width=8)
        table.add_column("Score", justify="right", width=7)
        table.add_column("Class", width=18)
        table.add_column("Setup", width=22)
        table.add_column("Risk Flags", width=30)

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
            )
        console.print(table)
        console.print(
            f"[dim]Score range: 0.0–1.0 | For evidence details run: vnalpha tui --date {target_date}[/dim]"
        )
    except ImportError:
        # Fallback if rich not available
        typer.echo(f"{'#':<4} {'Symbol':<8} {'Score':>7}  {'Class':<18}  {'Setup'}")
        typer.echo("-" * 65)
        for row in rows:
            typer.echo(
                f"{row['rank']:<4} {row['symbol']:<8} {row['score']:>7.3f}  {row.get('candidate_class', ''):<18}  {row.get('setup_type', '')}"
            )
        typer.echo(
            f"Score range: 0.0-1.0 | For evidence: vnalpha tui --date {target_date}"
        )


@app.command("tui")
def tui(
    date: Optional[str] = typer.Option(
        None, "--date", help="Reference date (YYYY-MM-DD). Default: today."
    ),
) -> None:
    """Launch the interactive research TUI."""
    try:
        from vnalpha.tui.app import VnAlphaApp
    except ImportError as err:
        typer.echo(
            "Error: 'textual' is required for the TUI. Install it with: pip install textual",
            err=True,
        )
        raise typer.Exit(code=1) from err

    VnAlphaApp(date=date).run()


# ---------------------------------------------------------------------------
# outcome sub-app
# ---------------------------------------------------------------------------
outcome_app = typer.Typer(name="outcome", help="Outcome tracking commands.")
app.add_typer(outcome_app, name="outcome")


@outcome_app.command("evaluate")
def outcome_evaluate(
    date: Optional[str] = typer.Option(None, "--date", help="Evaluate a single watchlist date"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date for range evaluation"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date for range evaluation"),
):
    """Evaluate candidate outcomes for a date or date range."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.outcomes.evaluator import evaluate_watchlist_date, evaluate_date_range
    from vnalpha.core.dates import resolve_date

    conn = get_connection()
    run_migrations(conn=conn)

    if date:
        target = resolve_date(date)
        result = evaluate_watchlist_date(conn, target)
        typer.echo(f"Evaluated {result['evaluated']} candidate-horizon pairs for {target}.")
        typer.echo(f"Persisted: {result['persisted']}, Errors: {result['errors']}")
    elif from_date and to_date:
        results = evaluate_date_range(conn, from_date, to_date)
        total = sum(r["evaluated"] for r in results)
        persisted = sum(r["persisted"] for r in results)
        typer.echo(f"Evaluated {len(results)} dates, {total} pairs, {persisted} persisted.")
    else:
        typer.echo("Provide --date or --from/--to.", err=True)
        raise typer.Exit(code=1)
    conn.close()


@outcome_app.command("candidates")
def outcome_candidates(
    date: str = typer.Option(..., "--date", help="Watchlist date"),
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show candidate outcomes for a date and horizon."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.outcomes.repositories import get_candidate_outcomes
    from vnalpha.core.dates import resolve_date
    from rich.console import Console
    from rich.table import Table

    conn = get_connection()
    run_migrations(conn=conn)
    rows = get_candidate_outcomes(conn, resolve_date(date), horizon)
    conn.close()

    console = Console()
    if not rows:
        console.print(f"[dim]No candidate outcomes for {date} horizon={horizon}[/dim]")
        return

    table = Table(title=f"Candidate Outcomes — {date} | Horizon {horizon}d")
    table.add_column("Symbol")
    table.add_column("Status")
    table.add_column("Score")
    table.add_column("Forward Rtn")
    table.add_column("Excess Rtn")
    table.add_column("Hit")
    table.add_column("Failure")

    for row in rows:
        fwd = f"{row['forward_return']:.2%}" if row["forward_return"] is not None else "—"
        exc = f"{row['excess_return_vs_vnindex']:.2%}" if row["excess_return_vs_vnindex"] is not None else "—"
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


@outcome_app.command("watchlist")
def outcome_watchlist(
    date: str = typer.Option(..., "--date", help="Watchlist date"),
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show watchlist outcome summary for a date and horizon."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.outcomes.repositories import get_watchlist_outcome
    from vnalpha.core.dates import resolve_date
    from rich.console import Console
    from rich.panel import Panel

    conn = get_connection()
    run_migrations(conn=conn)
    result = get_watchlist_outcome(conn, resolve_date(date), horizon)
    conn.close()

    console = Console()
    if result is None:
        console.print(f"[dim]No watchlist outcome for {date} horizon={horizon}[/dim]")
        return

    avg_fwd = f"{result['avg_forward_return']:.2%}" if result["avg_forward_return"] is not None else "—"
    avg_exc = f"{result['avg_excess_return']:.2%}" if result["avg_excess_return"] is not None else "—"
    hit_rate = f"{result['hit_rate']:.1%}" if result["hit_rate"] is not None else "—"
    fail_rate = f"{result['failure_rate']:.1%}" if result["failure_rate"] is not None else "—"
    lines = [
        f"Candidates: {result.get('candidate_count')}",
        f"Complete: {result.get('complete_count')} | Pending: {result.get('pending_count')} | Missing: {result.get('missing_data_count')}",
        f"Avg Forward Return: {avg_fwd}",
        f"Avg Excess Return: {avg_exc}",
        f"Hit Rate: {hit_rate}",
        f"Failure Rate: {fail_rate}",
    ]
    console.print(Panel("\n".join(lines), title=f"Watchlist Outcome — {date} | Horizon {horizon}d"))


@outcome_app.command("buckets")
def outcome_buckets(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show score bucket performance."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.outcomes.repositories import list_score_bucket_performance
    from rich.console import Console
    from rich.table import Table

    conn = get_connection()
    run_migrations(conn=conn)
    rows = list_score_bucket_performance(conn, horizon)
    conn.close()

    console = Console()
    if not rows:
        console.print(f"[dim]No score bucket data for horizon={horizon}[/dim]")
        return

    table = Table(title=f"Score Bucket Performance — Horizon {horizon}d")
    table.add_column("Bucket")
    table.add_column("Count")
    table.add_column("Avg Fwd Rtn")
    table.add_column("Hit Rate")
    table.add_column("Failure Rate")
    for row in rows:
        fwd = f"{row['avg_forward_return']:.2%}" if row["avg_forward_return"] is not None else "—"
        hit = f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
        fail = f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "—"
        table.add_row(row["score_bucket"], str(row["candidate_count"] or 0), fwd, hit, fail)
    console.print(table)


@outcome_app.command("setups")
def outcome_setups(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show setup type performance."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.outcomes.repositories import list_setup_type_performance
    from rich.console import Console
    from rich.table import Table

    conn = get_connection()
    run_migrations(conn=conn)
    rows = list_setup_type_performance(conn, horizon)
    conn.close()

    console = Console()
    if not rows:
        console.print(f"[dim]No setup type data for horizon={horizon}[/dim]")
        return

    table = Table(title=f"Setup Type Performance — Horizon {horizon}d")
    table.add_column("Setup Type")
    table.add_column("Count")
    table.add_column("Avg Fwd Rtn")
    table.add_column("Hit Rate")
    table.add_column("Failure Rate")
    for row in rows:
        fwd = f"{row['avg_forward_return']:.2%}" if row["avg_forward_return"] is not None else "—"
        hit = f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
        fail = f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "—"
        table.add_row(row["setup_type"], str(row["candidate_count"] or 0), fwd, hit, fail)
    console.print(table)


@outcome_app.command("risks")
def outcome_risks(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
):
    """Show risk flag performance."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.outcomes.repositories import list_risk_flag_performance
    from rich.console import Console
    from rich.table import Table

    conn = get_connection()
    run_migrations(conn=conn)
    rows = list_risk_flag_performance(conn, horizon)
    conn.close()

    console = Console()
    if not rows:
        console.print(f"[dim]No risk flag data for horizon={horizon}[/dim]")
        return

    table = Table(title=f"Risk Flag Performance — Horizon {horizon}d")
    table.add_column("Risk Flag")
    table.add_column("Count")
    table.add_column("Avg Fwd Rtn")
    table.add_column("Hit Rate")
    table.add_column("Failure Rate")
    for row in rows:
        fwd = f"{row['avg_forward_return']:.2%}" if row["avg_forward_return"] is not None else "—"
        hit = f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
        fail = f"{row['failure_rate']:.1%}" if row["failure_rate"] is not None else "—"
        table.add_row(row["risk_flag"], str(row["candidate_count"] or 0), fwd, hit, fail)
    console.print(table)


@outcome_app.command("report")
def outcome_report(
    horizon: int = typer.Option(20, "--horizon", help="Horizon in sessions"),
    date: Optional[str] = typer.Option(None, "--date", help="As-of date (default: latest)"),
):
    """Generate calibration report."""
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.outcomes.calibration import generate_calibration_report
    from vnalpha.core.dates import resolve_date
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    conn = get_connection()
    run_migrations(conn=conn)
    as_of = resolve_date(date) if date else None
    report = generate_calibration_report(conn, horizon, as_of_date=as_of)
    conn.close()

    console = Console()
    console.print(Panel(
        f"As-of date: {report['as_of_date']} | Horizon: {horizon} sessions\n"
        f"Pending: {report['pending_count']} | Missing: {report['missing_count']}\n"
        f"Score bucket monotone: {report['score_bucket_monotone']}\n"
        f"Best setup: {report.get('best_setup') or '—'} | Worst setup: {report.get('worst_setup') or '—'}\n"
        f"Worst risk flag: {report.get('worst_risk_flag') or '—'}\n\n"
        f"[dim]{report['interpretation_note']}[/dim]",
        title="Calibration Report",
    ))
    """Launch the interactive research TUI."""
    try:
        from vnalpha.tui.app import VnAlphaApp
    except ImportError as err:
        typer.echo(
            "Error: 'textual' is required for the TUI. Install it with: pip install textual",
            err=True,
        )
        raise typer.Exit(code=1) from err

    VnAlphaApp(date=date).run()


@app.command("cmd")
def cmd_runner(
    command: str = typer.Argument(..., help="Slash command to run, e.g. '/scan VN30'"),
    date: Optional[str] = typer.Option(
        None, "--date", help="Override date context (YYYY-MM-DD or 'today')."
    ),
) -> None:
    """Run a Phase 5.8 slash command in the research workspace.

    Examples:
        vnalpha cmd "/help"
        vnalpha cmd "/scan"
        vnalpha cmd "/explain FPT"
        vnalpha cmd "/filter score>=0.70"
        vnalpha cmd "/history --limit 20"
    """
    from vnalpha.commands.errors import (
        CommandError,
        CommandParseError,
        UnknownCommandError,
    )
    from vnalpha.commands.parser import parse as parse_command
    from vnalpha.commands.renderers.rich_renderer import render_result
    from vnalpha.commands.setup import build_default_registry
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.warehouse.session_repo import (
        create_research_session,
        finish_research_session,
    )

    # Parse command
    try:
        parsed = parse_command(command)
    except CommandParseError as exc:
        typer.echo(f"Parse error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # Override date option if --date passed to CLI
    if date:
        parsed.options["date"] = date

    # Open warehouse connection
    conn = get_connection()
    run_migrations(conn=conn)

    # Create research session
    session_id = create_research_session(
        conn,
        surface="cli",
        command_text=command,
        command_name=parsed.command_name,
        parsed_args={
            "positional": parsed.positional,
            "filters": [(f.key, f.op, f.value) for f in parsed.filters],
            "options": dict(parsed.options),
        },
    )

    # Build registry and run
    registry = build_default_registry()
    try:
        result = registry.execute(parsed, conn=conn, registry=registry, session_id=session_id)
    except UnknownCommandError as exc:
        finish_research_session(
            conn, session_id, status="FAILED",
            error={"error_type": "UnknownCommandError", "message": str(exc)},
        )
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except CommandError as exc:
        finish_research_session(
            conn, session_id, status="FAILED",
            error={"error_type": type(exc).__name__, "message": str(exc)},
        )
        typer.echo(f"Command error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        finish_research_session(
            conn, session_id, status="FAILED",
            error={"error_type": "RuntimeError", "message": str(exc)},
        )
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # Persist session result
    session_status = result.status if result.status == "SUCCESS" else "FAILED"
    if result.status == "VALIDATION_ERROR":
        session_status = "VALIDATION_ERROR"
    finish_research_session(
        conn,
        session_id,
        status=session_status,
        result_summary={"title": result.title, "summary": result.summary},
        error={"error_type": result.error.error_type, "message": result.error.message}
        if result.error
        else None,
    )

    # Render result
    try:
        from rich.console import Console
        render_result(result, console=Console())
    except ImportError:
        typer.echo(result.title)
        if result.summary:
            typer.echo(result.summary)

    # Non-zero exit for non-success
    if result.status != "SUCCESS":
        raise typer.Exit(code=1)


@app.command("ask")
def ask_runner(
    question: str = typer.Argument(..., help="Natural-language research question."),
    date: Optional[str] = typer.Option(None, "--date", help="Target date (YYYY-MM-DD or 'today')."),
    show_plan: bool = typer.Option(False, "--show-plan", help="Print the tool plan before answering."),
    trace: bool = typer.Option(False, "--trace", help="Print tool trace summary after answering."),
    no_execute: bool = typer.Option(False, "--no-execute", help="Show plan only; do not execute tools."),
) -> None:
    """Ask a natural-language research question. Phase 5.9 research assistant.

    Examples:
        vnalpha ask "Show strongest VN30 candidates today"
        vnalpha ask "Why is FPT in the watchlist?"
        vnalpha ask "Compare FPT, VNM, and MWG"
        vnalpha ask "Which candidates have weak data quality?"
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    from vnalpha.assistant.app import AssistantApp
    from vnalpha.assistant.errors import AssistantError
    from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
    from vnalpha.assistant.models import AssistantAnswer, RefusalMessage
    from vnalpha.warehouse.connection import get_connection
    from vnalpha.warehouse.migrations import run_migrations

    console = Console()

    resolved_date = None
    if date:
        resolved_date = resolve_date(date)

    conn = get_connection()
    run_migrations(conn=conn)

    try:
        llm_config = LLMGatewayConfig.from_env()
        llm_client = LLMGatewayClient(llm_config)
        assistant = AssistantApp(conn, surface="cli", llm_client=llm_client)
        result, plan = assistant.ask(question, date=resolved_date, no_execute=no_execute)
    except AssistantError as exc:
        console.print(f"[red]Assistant error: {exc}[/red]", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]Unexpected error: {exc}[/red]", err=True)
        raise typer.Exit(code=1) from exc

    # Show plan if requested (or if no_execute)
    if show_plan or no_execute:
        from vnalpha.assistant.planner import PlanBuilder
        pb = PlanBuilder()
        console.print(Panel(pb.preview(plan), title="Research Plan", border_style="blue"))

    if isinstance(result, RefusalMessage):
        console.print(Panel(
            f"[yellow]{result.reason}[/yellow]" +
            (f"\n\n[dim]Suggestion: {result.suggestion}[/dim]" if result.suggestion else ""),
            title="[red]Request Refused[/red]",
            border_style="red",
        ))
        raise typer.Exit(code=1)

    # Render answer
    assert isinstance(result, AssistantAnswer)
    answer_text = Text()
    answer_text.append(result.summary + "\n\n", style="bold")
    answer_text.append("Basis: ", style="dim")
    answer_text.append(result.basis + "\n")
    if result.risks_caveats:
        answer_text.append("Risks/caveats: ", style="dim yellow")
        answer_text.append(result.risks_caveats + "\n")
    if result.missing_data:
        answer_text.append("\nMissing data:\n", style="dim red")
        for item in result.missing_data:
            answer_text.append(f"  \u2022 {item}\n", style="red")
    console.print(Panel(answer_text, title="Research Answer", border_style="green"))

    if trace:
        console.print(Panel(result.tool_trace_summary or "(no trace)", title="Tool Trace", border_style="dim"))
