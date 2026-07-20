"""Tests for point-in-time RankingRun baseline evaluation v2."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.ranking_evaluation import (
    MIN_SUFFICIENT_SAMPLE,
    evaluate_ranking_run,
    get_ranking_evaluation,
)
from vnalpha.ranking_evaluation.evaluator import RankingEvaluationError
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


def _seed_classification(conn, symbol, sector="TECH"):
    conn.execute(
        """
        INSERT INTO symbol_classification_history (
            symbol, effective_from, source_snapshot_id, classification_source,
            exchange, security_type, lifecycle_status, listing_date,
            sector_code, sector_name, taxonomy_name, taxonomy_version
        ) SELECT ?, '2020-01-01', ?, 'fixture', 'HOSE', 'STOCK', 'ACTIVE',
                 '2020-01-01', ?, ?, 'ICB', 'v1'
        WHERE NOT EXISTS (
            SELECT 1 FROM symbol_classification_history WHERE symbol = ?
        )
        """,
        [symbol, f"snapshot-{symbol}", sector, sector, symbol],
    )


def _seed_outcome(
    conn,
    symbol,
    rank,
    excess,
    *,
    day="2026-01-05",
    horizon=20,
    max_gain=0.1,
    max_drawdown=-0.05,
    status="COMPLETE",
    policy_hash="hash123",
    momentum=None,
    component_score=None,
    sector="TECH",
):
    _seed_classification(conn, symbol, sector)
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, return_20d, feature_data_status
        ) VALUES (?, ?, ?, 'READY')
        ON CONFLICT (symbol, date) DO UPDATE SET return_20d = excluded.return_20d
        """,
        [symbol, day, momentum if momentum is not None else -rank / 100.0],
    )
    component = component_score if component_score is not None else rank / 100.0
    conn.execute(
        """
        INSERT INTO candidate_score (
            symbol, date, score, candidate_class, trend_score,
            relative_strength_score, volume_score, base_score,
            breakout_score, risk_quality_score, scoring_policy_id,
            scoring_policy_version, scoring_policy_hash, scoring_policy_status
        ) VALUES (?, ?, ?, 'WATCH', ?, ?, ?, ?, ?, ?, 'baseline', 'v2', ?, 'EXPERIMENTAL')
        ON CONFLICT (symbol, date) DO UPDATE SET
            trend_score = excluded.trend_score,
            relative_strength_score = excluded.relative_strength_score,
            volume_score = excluded.volume_score,
            base_score = excluded.base_score,
            breakout_score = excluded.breakout_score,
            risk_quality_score = excluded.risk_quality_score,
            scoring_policy_hash = excluded.scoring_policy_hash
        """,
        [symbol, day, 1.0 / rank, component, component, component, component, component, component, policy_hash],
    )
    conn.execute(
        """
        INSERT INTO candidate_outcome (
            symbol, watchlist_date, horizon_sessions, rank, score,
            excess_return_vs_vnindex, max_gain, max_drawdown, outcome_status,
            price_basis, adjustment_version, scoring_policy_id,
            scoring_policy_version, scoring_policy_hash, computed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RAW_UNADJUSTED', 'NONE',
                  'baseline', 'v2', ?, CAST(? AS DATE) + INTERVAL 30 DAY)
        """,
        [
            symbol,
            day,
            horizon,
            rank,
            1.0 / rank,
            excess,
            max_gain,
            max_drawdown,
            status,
            policy_hash,
            day,
        ],
    )


def test_metric_primitives_are_deterministic() -> None:
    assert hit_rate([0.1, -0.1, 0.2]) == pytest.approx(2 / 3)
    assert hit_rate([]) is None
    assert spearman_rank_correlation([1, 2, 3], [0.3, 0.2, 0.1]) == pytest.approx(1.0)
    assert sector_concentration({"A": 2, "B": 2}) == pytest.approx(0.5)


def test_baselines_use_identical_population_but_distinct_rankings(conn) -> None:
    for index in range(1, 16):
        _seed_outcome(
            conn,
            f"S{index}",
            rank=index,
            excess=0.2 - 0.01 * index,
            momentum=index / 100.0,
            component_score=(16 - index) / 100.0,
            sector="TECH" if index <= 8 else "BANK",
        )

    result = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert result.complete_population == 15
    assert result.sufficiency_status == "SUFFICIENT"
    strategies = {strategy.strategy: strategy for strategy in result.strategies}
    assert set(strategies) == {
        "packaged",
        "momentum_only",
        "equal_component",
        "unfiltered",
    }
    assert strategies["unfiltered"].sample_count == 15
    assert strategies["packaged"].sample_count == 5
    assert strategies["packaged"].selected_symbols != strategies["momentum_only"].selected_symbols
    assert strategies["equal_component"].selected_symbols != strategies["momentum_only"].selected_symbols
    assert all(strategy.sector_concentration is not None for strategy in strategies.values())


def test_incomplete_outcomes_are_explicit_partial_not_silently_dropped(conn) -> None:
    for index in range(1, 12):
        _seed_outcome(conn, f"S{index}", rank=index, excess=0.05)
    _seed_outcome(conn, "PENDINGX", rank=99, excess=0.0, status="PENDING")
    result = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert result.complete_population == 11
    assert result.incomplete_population == 1
    assert result.sufficiency_status == "PARTIAL"
    assert "not COMPLETE" in result.partial_reason


def test_mixed_policy_fails_closed(conn) -> None:
    _seed_outcome(conn, "A", rank=1, excess=0.1, policy_hash="hash123")
    _seed_outcome(conn, "B", rank=2, excess=0.1, policy_hash="other")
    with pytest.raises(RankingEvaluationError, match="scoring_policy_hash"):
        evaluate_ranking_run(conn, "2026-01-05", horizon=20)


def test_insufficient_sample_is_labeled(conn) -> None:
    for index in range(1, 4):
        _seed_outcome(conn, f"S{index}", rank=index, excess=0.05)
    result = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert result.sufficiency_status == "INSUFFICIENT"
    assert MIN_SUFFICIENT_SAMPLE > 3


def test_content_addressed_manifest_changes_only_when_evidence_changes(conn) -> None:
    for index in range(1, 12):
        _seed_outcome(conn, f"S{index}", rank=index, excess=0.05)
    first = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    repeated = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert first.manifest_id == repeated.manifest_id
    assert conn.execute(
        "SELECT COUNT(*) FROM ranking_evaluation_manifest_v2"
    ).fetchone()[0] == 1

    _seed_outcome(conn, "NEW", rank=20, excess=0.02)
    changed = evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    assert changed.manifest_id != first.manifest_id
    assert conn.execute(
        "SELECT COUNT(*) FROM ranking_evaluation_manifest_v2"
    ).fetchone()[0] == 2
    fetched = get_ranking_evaluation(conn, changed.manifest_id)
    assert fetched is not None
    assert fetched["dataset_hash"] == changed.dataset_hash


def test_turnover_is_computed_against_previous_same_policy_run(conn) -> None:
    for index in range(1, 12):
        _seed_outcome(conn, f"S{index}", rank=index, excess=0.05, day="2026-01-05")
    evaluate_ranking_run(conn, "2026-01-05", horizon=20, top_n=5)
    for index in range(1, 12):
        symbol = f"S{index + 2}"
        _seed_outcome(conn, symbol, rank=index, excess=0.05, day="2026-01-06")
    result = evaluate_ranking_run(conn, "2026-01-06", horizon=20, top_n=5)
    packaged = next(item for item in result.strategies if item.strategy == "packaged")
    assert packaged.turnover is not None
    assert packaged.turnover > 0
