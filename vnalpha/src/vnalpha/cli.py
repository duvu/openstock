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
