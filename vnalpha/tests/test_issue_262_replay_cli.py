"""CLI surface tests for issue #262: bounded replay/backtest command.

The deterministic replay engine is covered by test_issue_262_replay.py. These
tests cover the CLI command itself: it runs a fixed spec, persists an immutable
artifact, and both `replay run` and `replay show` read the same persisted
artifact via the shared reader. Future-data / contamination fails closed.
"""

from __future__ import annotations

import json

import duckdb
import pytest
from typer.testing import CliRunner

# Reuse the engine test's seeding helpers to build point-in-time evidence.
from tests.test_issue_262_replay import _seed_period
from vnalpha.cli import app
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    db_path = tmp_path / "warehouse.duckdb"
    conn = duckdb.connect(str(db_path))
    run_migrations(conn=conn, emit_observability=False)
    _seed_period(conn, "2026-01-05", prefix="S")
    _seed_period(conn, "2026-01-06", prefix="T")
    conn.close()

    # Point the CLI's get_connection at this warehouse.
    monkeypatch.setenv("VNALPHA_WAREHOUSE_PATH", str(db_path))
    return db_path


def _run(args):
    return CliRunner().invoke(app, args)


def test_replay_run_persists_and_reports_artifact(warehouse) -> None:
    result = _run(
        [
            "replay",
            "run",
            "--from",
            "2026-01-05",
            "--to",
            "2026-01-31",
            "--horizon",
            "20",
            "--top-n",
            "3",
            "--json",
        ]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["replay_id"]
    assert payload["period_count"] == 2
    assert payload["spec_hash"]
    assert payload["result_hash"]


def test_replay_run_and_show_read_the_same_artifact(warehouse) -> None:
    run_result = _run(
        [
            "replay",
            "run",
            "--from",
            "2026-01-05",
            "--to",
            "2026-01-31",
            "--horizon",
            "20",
            "--top-n",
            "3",
            "--json",
        ]
    )
    assert run_result.exit_code == 0, run_result.output
    run_payload = json.loads(run_result.stdout)

    show_result = _run(["replay", "show", run_payload["replay_id"], "--json"])
    assert show_result.exit_code == 0, show_result.output
    show_payload = json.loads(show_result.stdout)

    # The run output and a later show read the identical persisted artifact.
    assert show_payload == run_payload


def test_replay_run_is_reproducible(warehouse) -> None:
    args = [
        "replay",
        "run",
        "--from",
        "2026-01-05",
        "--to",
        "2026-01-31",
        "--horizon",
        "20",
        "--top-n",
        "3",
        "--json",
    ]
    first = json.loads(_run(args).stdout)
    second = json.loads(_run(args).stdout)
    # Identical inputs reproduce identical content-addressed results.
    assert first["replay_id"] == second["replay_id"]
    assert first["result_hash"] == second["result_hash"]
    assert first["spec_hash"] == second["spec_hash"]


def test_replay_show_unknown_id_fails(warehouse) -> None:
    result = _run(["replay", "show", "does-not-exist", "--json"])
    assert result.exit_code != 0


def test_replay_unsupported_benchmark_fails_closed(warehouse) -> None:
    # horizon with no matching outcomes yields an empty replay; a bad price
    # basis (contamination) must fail closed with a non-zero exit.
    result = _run(
        [
            "replay",
            "run",
            "--from",
            "2026-01-05",
            "--to",
            "2026-01-31",
            "--horizon",
            "20",
            "--top-n",
            "3",
            "--price-basis",
            "ADJUSTED",
        ]
    )
    assert result.exit_code != 0
