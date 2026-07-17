from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest

from vnalpha.data_availability.policy import DEFAULT_POLICY
from vnalpha.data_provisioning.service import (
    DataProvisioningDependencies,
    DataProvisioningRequest,
    DataProvisioningService,
    ProvisioningStatus,
)
from vnalpha.outcomes.aggregations import aggregate_watchlist_outcome
from vnalpha.outcomes.basis import ActionOverlapStatus, assess_observation_lineage
from vnalpha.outcomes.evaluator import evaluate_watchlist_date
from vnalpha.scoring.generate_watchlist import save_watchlist
from vnalpha.scoring.policy import (
    BASELINE_SCORING_POLICY,
    PolicyLifecycleStatus,
    ScoringPolicy,
    resolve_scoring_policy,
)
from vnalpha.scoring.score import compute_composite_score
from vnalpha.symbol_memory.adapters import CandidateScoreSnapshot
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import save_candidate_score


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(connection, emit_observability=False)
    yield connection
    connection.close()


def _features() -> dict[str, float]:
    return {
        "close": 110.0,
        "ma20": 100.0,
        "ma50": 95.0,
        "ma100": 90.0,
        "ma20_slope": 0.02,
        "rs_20d_vs_vnindex": 0.03,
        "rs_60d_vs_vnindex": 0.01,
        "volume_ratio": 1.6,
        "base_range_30d": 0.06,
        "close_strength": 0.8,
        "distance_to_52w_high": -0.02,
        "distance_to_ma20": 0.1,
    }


def _seed_watchlist(conn: duckdb.DuckDBPyConnection, symbol: str = "FPT") -> None:
    policy = BASELINE_SCORING_POLICY
    conn.execute(
        "INSERT INTO daily_watchlist "
        "(date, rank, symbol, score, candidate_class, scoring_policy_id, "
        "scoring_policy_version, scoring_policy_hash, scoring_policy_status) "
        "VALUES ('2026-07-01', 1, ?, 0.8, 'STRONG_CANDIDATE', ?, ?, ?, ?)",
        [
            symbol,
            policy.policy_id,
            policy.version,
            policy.payload_hash,
            policy.lifecycle_status.value,
        ],
    )


def test_policy_identity_is_derived_and_effective_dates_are_enforced() -> None:
    policy = BASELINE_SCORING_POLICY
    altered = ScoringPolicy.from_payload(
        policy_id=policy.policy_id,
        version="v1.0-test",
        lifecycle_status=PolicyLifecycleStatus.EXPERIMENTAL,
        effective_from=policy.effective_from,
        payload={"weights": {"trend": 1.0}},
    )

    assert altered.payload_hash != policy.payload_hash
    with pytest.raises(TypeError):
        ScoringPolicy(
            policy_id=policy.policy_id,
            version=policy.version,
            lifecycle_status=policy.lifecycle_status,
            effective_from=policy.effective_from,
            effective_to=policy.effective_to,
            payload=policy.payload,
            payload_hash="0" * 64,
        )
    with pytest.raises(ValueError, match="not effective"):
        resolve_scoring_policy(
            policy.policy_id,
            policy.version,
            as_of_date=date(2023, 12, 31),
        )


def test_score_persistence_rejects_missing_or_spoofed_policy(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    result = compute_composite_score(_features())
    missing = dict(result)
    missing.pop("scoring_policy_hash")
    spoofed = dict(result)
    spoofed["scoring_policy_status"] = PolicyLifecycleStatus.ACCEPTED.value

    with pytest.raises(ValueError, match="policy identity"):
        save_candidate_score(conn, "FPT", "2026-07-01", missing)
    with pytest.raises(ValueError, match="policy identity"):
        save_candidate_score(conn, "FPT", "2026-07-01", spoofed)
    assert conn.execute("SELECT COUNT(*) FROM candidate_score").fetchone() == (0,)


@pytest.mark.parametrize("use_affected_range", [False, True])
def test_conflict_and_affected_range_overlap_fail_closed(
    conn: duckdb.DuckDBPyConnection,
    use_affected_range: bool,
) -> None:
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, price_basis) VALUES "
        "('FPT', '2026-07-01', '1D', 100, 'VCI', 'RAW_UNADJUSTED'), "
        "('FPT', '2026-07-02', '1D', 101, 'VCI', 'RAW_UNADJUSTED')"
    )
    status = "CONFIRMED" if use_affected_range else "CONFLICT"
    action_date = "2026-06-01" if use_affected_range else "2026-07-01"
    conn.execute(
        "INSERT INTO corporate_action "
        "(revision_id, action_id, revision_number, symbol, action_type, ex_date, "
        "revision_hash, canonical_status, contract_version) "
        "VALUES ('rev-1', 'action-1', 1, 'FPT', 'STOCK_SPLIT', ?, "
        "'hash-1', ?, 'v1')",
        [action_date, status],
    )
    if use_affected_range:
        conn.execute(
            "INSERT INTO corporate_action_affected_range "
            "(signal_id, action_id, revision_id, symbol, affected_from_date, "
            "affected_to_date, reason) VALUES "
            "('signal-1', 'action-1', 'rev-1', 'FPT', '2026-06-01', "
            "'2026-07-05', 'REVISED_ACTION')"
        )

    lineage = assess_observation_lineage(conn, "FPT", "2026-07-01", "2026-07-02")

    assert lineage.action_overlap_status is ActionOverlapStatus.INVALID
    assert lineage.invalidation_reason == "RAW_SERIES_CORPORATE_ACTION_OVERLAP"
    assert lineage.corporate_action_lineage


def test_evaluator_checks_actual_entry_bar_and_marks_run_partial(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed_watchlist(conn)
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, price_basis) VALUES "
        "('FPT', '2026-06-30', '1D', 100, 'VCI', 'ADJUSTED'), "
        "('FPT', '2026-07-02', '1D', 101, 'VCI', 'RAW_UNADJUSTED')"
    )

    result = evaluate_watchlist_date(conn, "2026-07-01", horizons=[1])

    outcome = conn.execute(
        "SELECT outcome_status, price_basis, adjustment_methodology, "
        "adjustment_version, scoring_policy_hash FROM candidate_outcome"
    ).fetchone()
    run = conn.execute(
        "SELECT status, price_basis, adjustment_methodology, adjustment_version "
        "FROM outcome_evaluation_run WHERE evaluation_run_id=?",
        [result["evaluation_run_id"]],
    ).fetchone()
    assert outcome == (
        "PARTIAL",
        "RAW_UNADJUSTED",
        "NONE",
        "raw-unadjusted-v1",
        BASELINE_SCORING_POLICY.payload_hash,
    )
    assert run == ("PARTIAL", "UNKNOWN", "UNKNOWN", "UNKNOWN")


def test_legacy_complete_outcome_is_ineligible_for_aggregates(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    conn.execute(
        "INSERT INTO candidate_outcome "
        "(symbol, watchlist_date, horizon_sessions, outcome_status, forward_return) "
        "VALUES ('FPT', '2026-07-01', 20, 'COMPLETE', 0.25)"
    )

    summary = aggregate_watchlist_outcome(conn, "2026-07-01", 20)

    assert summary.complete_count == 0
    assert summary.invalid_count == 1
    assert summary.avg_forward_return is None


def test_watchlist_replacement_requires_explicit_policy_rebuild(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    result = compute_composite_score(_features())
    save_candidate_score(conn, "FPT", "2026-07-01", result)
    conn.execute(
        "INSERT INTO daily_watchlist "
        "(date, rank, symbol, score, candidate_class, scoring_policy_id, "
        "scoring_policy_version, scoring_policy_hash, scoring_policy_status) "
        "VALUES ('2026-07-01', 1, 'OLD', 0.9, 'STRONG_CANDIDATE', "
        "'other-policy', 'v9', ?, 'EXPERIMENTAL')",
        ["f" * 64],
    )

    with pytest.raises(ValueError, match="explicit rebuild"):
        save_watchlist(conn, "2026-07-01", allow_policy_rebuild=False)
    assert conn.execute(
        "SELECT symbol FROM daily_watchlist WHERE date='2026-07-01'"
    ).fetchone() == ("OLD",)

    assert save_watchlist(conn, "2026-07-01", allow_policy_rebuild=True) == 1
    assert conn.execute(
        "SELECT symbol, scoring_policy_hash FROM daily_watchlist "
        "WHERE date='2026-07-01'"
    ).fetchone() == ("FPT", BASELINE_SCORING_POLICY.payload_hash)


def test_incomplete_score_scope_is_partial_and_policy_is_auditable(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    policy = BASELINE_SCORING_POLICY

    def generate_watchlist(*_args, **_kwargs):
        return {
            "scored": 1,
            "saved": 1,
            "requested": 2,
            "missing": 1,
            "scoring_policy_id": policy.policy_id,
            "scoring_policy_version": policy.version,
            "scoring_policy_hash": policy.payload_hash,
            "scoring_policy_status": policy.lifecycle_status.value,
        }

    service = DataProvisioningService(
        conn,
        dependencies=DataProvisioningDependencies(
            generate_watchlist=generate_watchlist
        ),
    )

    result = service.execute(
        DataProvisioningRequest(
            "build",
            "score",
            symbols=("FPT", "VNM"),
            date="2026-07-01",
        )
    )

    assert result.status is ProvisioningStatus.PARTIAL
    assert result.counts["missing"] == 1
    assert result.warnings
    assert result.lineage["scoring_policy_hash"] == policy.payload_hash


def test_readiness_and_memory_require_policy_lineage() -> None:
    required = set(DEFAULT_POLICY.required_lineage_fields)

    assert {
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    } <= required
    with pytest.raises(TypeError):
        CandidateScoreSnapshot(
            symbol="FPT",
            as_of_date=date(2026, 7, 1),
            score=0.8,
            candidate_class="STRONG_CANDIDATE",
            setup_type="BREAKOUT_ATTEMPT",
            correlation_id="test",
            persisted_at=datetime.now(UTC),
        )
