"""Bounded CLI replay/backtest command for issue #262.

Replays one fixed historical ranking specification over exact point-in-time
OpenStock evidence and persists a content-addressed artifact. Both the CLI and
the TUI read that same persisted artifact via ``get_replay``, so a run and a
later inspection return identical reproducible results. There is no future-data
fallback, arbitrary code execution or external action capability: the command
only reads persisted candidate outcomes and writes one immutable replay row.
"""

from __future__ import annotations

import json

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle

app = typer.Typer(name="replay", help="Bounded point-in-time ranking replay/backtest.")


def _spec_from_options(
    *,
    start_date: str,
    end_date: str,
    horizon_sessions: int,
    top_n: int,
    cost_bps: float,
    price_basis: str,
    scoring_policy_hash: str | None,
):
    from vnalpha.replay.engine import ReplaySpec

    return ReplaySpec(
        start_date=start_date,
        end_date=end_date,
        horizon_sessions=horizon_sessions,
        top_n=top_n,
        cost_bps=cost_bps,
        price_basis=price_basis,
        scoring_policy_hash=scoring_policy_hash,
    )


@app.command("run")
def run(
    start_date: str = typer.Option(..., "--from", help="Inclusive start date."),
    end_date: str = typer.Option(..., "--to", help="Inclusive end date."),
    horizon_sessions: int = typer.Option(
        20, "--horizon", help="Declared holding horizon."
    ),
    top_n: int = typer.Option(10, "--top-n", help="Declared top-N selection size."),
    cost_bps: float = typer.Option(
        0.0, "--cost-bps", help="Per-rebalance cost in bps."
    ),
    price_basis: str = typer.Option(
        "RAW_UNADJUSTED", "--price-basis", help="Declared price basis."
    ),
    scoring_policy_hash: str | None = typer.Option(
        None, "--policy-hash", help="Pin the exact RankingPolicy hash."
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run one fixed replay specification and persist its immutable artifact."""
    set_correlation_id()
    with command_lifecycle("replay run"):
        from vnalpha.replay.engine import (
            ReplayContaminationError,
            get_replay,
            run_replay,
        )
        from vnalpha.warehouse.connection import get_connection
        from vnalpha.warehouse.migrations import run_migrations

        spec = _spec_from_options(
            start_date=start_date,
            end_date=end_date,
            horizon_sessions=horizon_sessions,
            top_n=top_n,
            cost_bps=cost_bps,
            price_basis=price_basis,
            scoring_policy_hash=scoring_policy_hash,
        )
        conn = get_connection()
        run_migrations(conn=conn)
        try:
            result = run_replay(conn, spec, persist=True)
            # Read back through the shared persisted-artifact reader so the CLI
            # reports exactly what the TUI would show.
            artifact = get_replay(conn, result.replay_id)
        except ReplayContaminationError as exc:
            # Future-data / mixed-basis / policy contamination fails closed.
            raise typer.BadParameter(str(exc)) from exc
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        finally:
            conn.close()

        _render(artifact, json_output=json_output)


@app.command("show")
def show(
    replay_id: str = typer.Argument(..., help="Persisted replay identifier."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show a persisted replay artifact (the same read path the TUI uses)."""
    with command_lifecycle("replay show"):
        from vnalpha.replay.engine import get_replay
        from vnalpha.warehouse.connection import get_connection

        conn = get_connection()
        try:
            artifact = get_replay(conn, replay_id)
        finally:
            conn.close()
        if artifact is None:
            raise typer.BadParameter(f"No persisted replay with id {replay_id!r}")
        _render(artifact, json_output=json_output)


def _render(artifact: dict[str, object] | None, *, json_output: bool) -> None:
    if artifact is None:
        raise typer.BadParameter("Replay produced no persisted artifact")
    if json_output:
        typer.echo(json.dumps(artifact, sort_keys=True, default=str))
        return
    typer.echo(f"Replay: {artifact['replay_id']}")
    typer.echo(f"  spec_hash:   {artifact['spec_hash']}")
    typer.echo(f"  result_hash: {artifact['result_hash']}")
    typer.echo(f"  dataset_hash:{artifact['dataset_hash']}")
    typer.echo(f"  periods:     {artifact['period_count']}")
    typer.echo(f"  total_return:{artifact['total_return']}")
    typer.echo(f"  max_drawdown:{artifact['max_drawdown']}")
    typer.echo(f"  mean_turnover:{artifact['mean_turnover']}")
    typer.echo(f"  mean_sector_concentration:{artifact['mean_sector_concentration']}")
    exclusions = artifact.get("exclusions") or []
    caveats = artifact.get("caveats") or []
    if exclusions:
        typer.echo(f"  exclusions:  {', '.join(map(str, exclusions))}")
    if caveats:
        typer.echo(f"  caveats:     {', '.join(map(str, caveats))}")


__all__ = ["app"]
