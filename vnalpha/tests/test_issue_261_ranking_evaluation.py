"""Tests for issue #261: RankingRun baseline evaluation."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.ranking_evaluation import (
    MIN_SUFFICIENT_SAMPLE,
    evaluate_ranking_run,
    get_ranking_evaluation,
)
from vnalpha.ranking_evaluation.metrics import (
    hit_rate,
    sector_concentration,
    spearman_rank_correlation,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _seed_outcome(
    conn,
    symbol,
    rank,
    excess,
    *,
    date="2026-01-05",
    horizon=20,
    max_gain=0.1,
    max_drawdown=-0.05,
    status="COMPLETE",
):
    conn.execute(
        """
        INSERT INTO candidate_outcome
            (symbol, watchlist_date, horizon_sessions, rank, score,
             excess_return_vs_vnindex, max_gain, max_drawdown, outcome_status,
             price_basis, scoring_policy_id, scoring_policy_version,
             scoring_policy_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RAW_UNADJUSTED',
                'baseline', 'v1', 'hash123')
        """,
        [
            symbol,
            date,
            horizon,
            rank,
            1.0 / rank,
            excess,
            max_gain,
            max_drawdown,
            status,
        ],
    )


def test_metric_primitives_are_deterministic() -> None:
    assert hit_rate([0.1, -0.1, 0.2]) == pytest.approx(2 / 3)
    assert hit_rate([]) is None
    # Perfectly informative ranking: best rank -> best outcome.
    corr = spearman_rank_correlation([1, 2, 3], [0.3, 0.2, 0.1])
    assert corr == pytest.approx(1.0)
    assert sector_concentration({"A": 2, "B": 2}) == pytest.approx(0.5)


def test_baselines_use_identical_population(conn) -> None:
    for i in range(1, 16):
        _seed_outcome(conn, f"S{i}", rank=i, excess=0.2 - 0.01 * i)

    result = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert result.complete_population == 15
    assert result.sufficiency_status == "SUFFICIENT"

    strategies = {s.strategy: s for s in result.strategies}
    assert set(strategies) == {
        "packaged",
        "momentum_only",
        "equal_weight",
        "unfiltered",
    }
    # Unfiltered spans the whole eligible population; top-N strategies are bounded.
    assert strategies["unfiltered"].sample_count == 15
    assert strategies["packaged"].sample_count == 5
    assert strategies["momentum_only"].sample_count == 5


def test_insufficient_sample_is_labeled(conn) -> None:
    for i in range(1, 4):  # only 3 < MIN_SUFFICIENT_SAMPLE
        _seed_outcome(conn, f"S{i}", rank=i, excess=0.05)
    result = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert result.complete_population == 3
    assert result.sufficiency_status == "INSUFFICIENT"
    assert result.partial_reason is not None
    assert MIN_SUFFICIENT_SAMPLE > 3


def test_incomplete_outcomes_excluded_from_population(conn) -> None:
    for i in range(1, 12):
        _seed_outcome(conn, f"S{i}", rank=i, excess=0.05)
    # A pending outcome must not enter the eligible population.
    _seed_outcome(conn, "PENDINGX", rank=99, excess=0.0, status="PENDING")
    result = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert result.complete_population == 11


def test_manifest_is_immutable_not_rewritten(conn) -> None:
    for i in range(1, 12):
        _seed_outcome(conn, f"S{i}", rank=i, excess=0.05)
    r1 = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    r2 = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    # Second evaluation for the same key does not create a second manifest.
    count = conn.execute("SELECT COUNT(*) FROM ranking_evaluation_manifest").fetchone()[
        0
    ]
    assert count == 1
    # get_ranking_evaluation reproduces the persisted result from source rows.
    fetched = get_ranking_evaluation(conn, r1.manifest_id)
    assert fetched is not None
    assert fetched["eligible_population"] == 11
    assert {s["strategy"] for s in fetched["strategies"]} == {
        "packaged",
        "momentum_only",
        "equal_weight",
        "unfiltered",
    }
    assert r2.manifest_id != r1.manifest_id  # fresh object, same persisted key


def test_packaged_informativeness_shows_in_rank_correlation(conn) -> None:
    # Rank order aligns with outcomes -> positive rank correlation for packaged.
    for i in range(1, 12):
        _seed_outcome(conn, f"S{i}", rank=i, excess=0.3 - 0.02 * i)
    result = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=11)
    packaged = next(s for s in result.strategies if s.strategy == "packaged")
    assert packaged.rank_correlation is not None
    assert packaged.rank_correlation > 0
