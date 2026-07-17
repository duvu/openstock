from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import duckdb
import pytest
import typer
from typer.testing import CliRunner

from vnalpha.outcomes.basis import (
    ActionOverlapStatus,
    BasisValidationError,
    assess_observation_lineage,
)
from vnalpha.scoring.policy import (
    BASELINE_SCORING_POLICY,
    PolicyLifecycleStatus,
    ScoringPolicy,
)
from vnalpha.scoring.score import compute_composite_score
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


def test_baseline_policy_is_immutable_hashed_and_reproduces_v1_output() -> None:
    policy = BASELINE_SCORING_POLICY

    assert policy.policy_id == "openstock-candidate-score"
    assert policy.version == "v1.0"
    assert policy.lifecycle_status is PolicyLifecycleStatus.EXPERIMENTAL
    assert len(policy.payload_hash) == 64
    assert (
        policy.payload_hash
        == ScoringPolicy.from_payload(
            policy_id=policy.policy_id,
            version=policy.version,
            lifecycle_status=policy.lifecycle_status,
            effective_from=policy.effective_from,
            payload=policy.payload,
        ).payload_hash
    )
    with pytest.raises((FrozenInstanceError, TypeError)):
        policy.version = "v2"

    assert compute_composite_score(_features(), policy=policy) == {
        "score": 0.855,
        "candidate_class": "STRONG_CANDIDATE",
        "setup_type": "BREAKOUT_ATTEMPT",
        "trend_score": 1.0,
        "relative_strength_score": 0.7,
        "volume_score": 0.8,
        "base_score": 0.6,
        "breakout_score": 1.0,
        "risk_quality_score": 1.0,
        "risk_flags": [],
        "scoring_policy_id": policy.policy_id,
        "scoring_policy_version": policy.version,
        "scoring_policy_hash": policy.payload_hash,
        "scoring_policy_status": "EXPERIMENTAL",
    }


def test_score_replay_is_idempotent_but_different_hash_cannot_overwrite(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    result = compute_composite_score(_features(), policy=BASELINE_SCORING_POLICY)
    save_candidate_score(conn, "FPT", "2026-07-01", result)
    save_candidate_score(conn, "FPT", "2026-07-01", result)

    changed = dict(result)
    changed["scoring_policy_hash"] = "0" * 64
    with pytest.raises(ValueError, match="policy hash"):
        save_candidate_score(conn, "FPT", "2026-07-01", changed)

    row = conn.execute(
        "SELECT scoring_policy_id, scoring_policy_hash FROM candidate_score"
    ).fetchone()
    assert row == (
        BASELINE_SCORING_POLICY.policy_id,
        BASELINE_SCORING_POLICY.payload_hash,
    )


def test_legacy_score_requires_explicit_policy_rebuild(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    conn.execute(
        "INSERT INTO candidate_score "
        "(symbol, date, score, candidate_class) "
        "VALUES ('FPT', '2026-07-01', 0.1, 'IGNORE')"
    )
    result = compute_composite_score(_features(), policy=BASELINE_SCORING_POLICY)

    with pytest.raises(ValueError, match="explicit rebuild"):
        save_candidate_score(conn, "FPT", "2026-07-01", result)

    save_candidate_score(
        conn,
        "FPT",
        "2026-07-01",
        result,
        allow_policy_rebuild=True,
    )

    row = conn.execute(
        "SELECT score, scoring_policy_hash FROM candidate_score "
        "WHERE symbol='FPT' AND date='2026-07-01'"
    ).fetchone()
    assert row == (0.855, BASELINE_SCORING_POLICY.payload_hash)


def test_shared_provisioning_forwards_explicit_rebuild_scope(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    from vnalpha.data_provisioning.service import (
        DataProvisioningDependencies,
        DataProvisioningRequest,
        DataProvisioningService,
    )

    received: dict[str, Any] = {}

    def generate_watchlist(
        _conn: duckdb.DuckDBPyConnection, **kwargs: Any
    ) -> dict[str, int]:
        received.update(kwargs)
        return {"scored": 0, "saved": 0}

    service = DataProvisioningService(
        conn,
        dependencies=DataProvisioningDependencies(
            generate_watchlist=generate_watchlist
        ),
    )
    service.execute(
        DataProvisioningRequest(
            "build",
            "score",
            symbols=("FPT",),
            date="2026-07-01",
            rebuild_policy=True,
        )
    )

    assert received["universe"] == ["FPT"]
    assert received["rebuild_policy"] is True


def test_legacy_migration_adds_policy_and_basis_lineage_columns(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    expected = {
        "candidate_score": {"scoring_policy_id", "scoring_policy_hash"},
        "daily_watchlist": {"scoring_policy_id", "scoring_policy_hash"},
        "candidate_outcome": {
            "price_basis",
            "benchmark_price_basis",
            "adjustment_methodology",
            "action_overlap_status",
            "invalidation_reason",
        },
        "outcome_evaluation_run": {
            "price_basis",
            "adjustment_methodology",
        },
    }
    for table, required in expected.items():
        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=?",
                [table],
            ).fetchall()
        }
        assert required <= columns


def test_mixed_or_unknown_basis_fails_closed(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, price_basis) VALUES "
        "('FPT', '2026-07-01', '1D', 100, 'VCI', 'RAW_UNADJUSTED'), "
        "('FPT', '2026-07-02', '1D', 101, 'VCI', 'ADJUSTED')"
    )

    with pytest.raises(BasisValidationError, match="mixed price basis"):
        assess_observation_lineage(conn, "FPT", "2026-07-01", "2026-07-02")

    conn.execute("UPDATE canonical_ohlcv SET price_basis=NULL")
    with pytest.raises(BasisValidationError, match="unknown price basis"):
        assess_observation_lineage(conn, "FPT", "2026-07-01", "2026-07-02")


@pytest.mark.parametrize("action_type", ["CASH_DIVIDEND", "STOCK_SPLIT"])
def test_raw_observation_with_action_overlap_is_explicitly_invalid(
    conn: duckdb.DuckDBPyConnection, action_type: str
) -> None:
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, price_basis) VALUES "
        "('FPT', '2026-07-01', '1D', 100, 'VCI', 'RAW_UNADJUSTED'), "
        "('FPT', '2026-07-10', '1D', 101, 'VCI', 'RAW_UNADJUSTED')"
    )
    conn.execute(
        "INSERT INTO corporate_action "
        "(revision_id, action_id, revision_number, symbol, action_type, ex_date, "
        "revision_hash, canonical_status, contract_version) "
        "VALUES ('rev-1', 'action-1', 1, 'FPT', ?, '2026-07-05', "
        "'hash-1', 'CONFIRMED', 'v1')",
        [action_type],
    )

    lineage = assess_observation_lineage(conn, "FPT", "2026-07-01", "2026-07-10")

    assert lineage.price_basis == "RAW_UNADJUSTED"
    assert lineage.adjustment_methodology == "NONE"
    assert lineage.action_overlap_status is ActionOverlapStatus.INVALID
    assert lineage.invalidation_reason == "RAW_SERIES_CORPORATE_ACTION_OVERLAP"
    assert lineage.overlapping_action_types == (action_type,)


def _seed_outcome_window(
    conn: duckdb.DuckDBPyConnection, *, exit_basis: str = "RAW_UNADJUSTED"
) -> None:
    conn.execute(
        "INSERT INTO daily_watchlist "
        "(date, rank, symbol, score, candidate_class, scoring_policy_id, "
        "scoring_policy_version, scoring_policy_hash, scoring_policy_status) "
        "VALUES ('2026-07-01', 1, 'FPT', 0.8, 'STRONG_CANDIDATE', ?, ?, ?, ?)",
        [
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )
    conn.execute(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, high, low, close, selected_provider, price_basis) "
        "VALUES "
        "('FPT', '2026-07-01', '1D', 101, 99, 100, 'VCI', 'RAW_UNADJUSTED'), "
        "('FPT', '2026-07-02', '1D', 103, 101, 102, 'VCI', ?), "
        "('VNINDEX', '2026-07-01', '1D', 1201, 1199, 1200, 'VCI', 'RAW_UNADJUSTED'), "
        "('VNINDEX', '2026-07-02', '1D', 1203, 1201, 1202, 'VCI', 'RAW_UNADJUSTED')",
        [exit_basis],
    )


def test_evaluator_invalidates_action_on_horizon_exit_and_preserves_raw_rows(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    from vnalpha.outcomes.evaluator import evaluate_watchlist_date

    _seed_outcome_window(conn)
    evaluate_watchlist_date(conn, "2026-07-01", horizons=[1])
    assert conn.execute(
        "SELECT outcome_status FROM candidate_outcome "
        "WHERE symbol='FPT' AND horizon_sessions=1"
    ).fetchone() == ("COMPLETE",)
    conn.execute(
        "INSERT INTO corporate_action "
        "(revision_id, action_id, revision_number, symbol, action_type, ex_date, "
        "revision_hash, canonical_status, contract_version) "
        "VALUES ('rev-exit', 'action-exit', 1, 'FPT', 'STOCK_SPLIT', "
        "'2026-07-02', 'hash-exit', 'CONFIRMED', 'v1')"
    )

    result = evaluate_watchlist_date(conn, "2026-07-01", horizons=[1])

    row = conn.execute(
        "SELECT outcome_status, price_basis, adjustment_methodology, "
        "action_overlap_status, invalidation_reason, forward_return "
        "FROM candidate_outcome WHERE symbol='FPT' AND horizon_sessions=1"
    ).fetchone()
    assert result["errors"] == 0
    assert row == (
        "INVALID",
        "RAW_UNADJUSTED",
        "NONE",
        "INVALID",
        "RAW_SERIES_CORPORATE_ACTION_OVERLAP",
        None,
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM canonical_ohlcv WHERE symbol='FPT'"
    ).fetchone() == (2,)


def test_evaluator_rejects_mixed_basis_across_observation_window(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    from vnalpha.outcomes.evaluator import evaluate_watchlist_date

    _seed_outcome_window(conn, exit_basis="ADJUSTED")

    evaluate_watchlist_date(conn, "2026-07-01", horizons=[1])

    row = conn.execute(
        "SELECT outcome_status, price_basis, adjustment_methodology, "
        "action_overlap_status, invalidation_reason "
        "FROM candidate_outcome WHERE symbol='FPT' AND horizon_sessions=1"
    ).fetchone()
    assert row is not None
    assert row[:4] == ("INVALID", "UNKNOWN", "UNKNOWN", "INVALID")
    assert "mixed price basis" in row[4]


def test_score_cli_discloses_selected_policy_identity(
    conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.cli_app import score as score_command
    from vnalpha.data_provisioning.service import (
        DataProvisioningResult,
        ProvisioningStatus,
    )
    from vnalpha.warehouse import connection

    monkeypatch.setattr(connection, "get_connection", lambda: conn)
    received_request = []

    def execute(_conn: duckdb.DuckDBPyConnection, request: Any):
        received_request.append(request)
        return DataProvisioningResult(
            status=ProvisioningStatus.SUCCESS,
            operation="build",
            artifact="score",
            correlation_id="qa-policy",
            counts={"scored": 1, "saved": 1},
            resolved_date="2026-07-01",
        )

    monkeypatch.setattr(
        score_command,
        "_execute",
        execute,
    )
    app = typer.Typer()
    score_command.register(app)

    result = CliRunner().invoke(
        app,
        [
            "--date",
            "2026-07-01",
            "--symbols",
            "FPT",
            "--scoring-policy",
            "openstock-candidate-score@v1.0",
            "--rebuild-policy",
        ],
    )

    assert result.exit_code == 0
    assert "openstock-candidate-score@v1.0" in result.output
    assert "EXPERIMENTAL" in result.output
    assert BASELINE_SCORING_POLICY.payload_hash in result.output
    assert "rebuild=explicit" in result.output
    assert received_request[0].rebuild_policy is True


def test_outcome_cli_discloses_basis_and_action_status(
    conn: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vnalpha.cli_app.outcome_summary import outcome_candidates
    from vnalpha.outcomes.models import CandidateOutcomeRecord, OutcomeStatus
    from vnalpha.outcomes.repositories import upsert_candidate_outcome
    from vnalpha.warehouse import connection

    upsert_candidate_outcome(
        conn,
        CandidateOutcomeRecord(
            symbol="FPT",
            watchlist_date="2026-07-01",
            horizon_sessions=20,
            score=0.75,
            outcome_status=OutcomeStatus.COMPLETE.value,
            price_basis="RAW_UNADJUSTED",
            benchmark_price_basis="RAW_UNADJUSTED",
            adjustment_methodology="NONE",
            action_overlap_status="CLEAR",
        ),
    )
    monkeypatch.setattr(connection, "get_connection", lambda: conn)
    app = typer.Typer()
    app.command("candidates")(outcome_candidates)

    result = CliRunner().invoke(
        app,
        ["--date", "2026-07-01", "--horizon", "20"],
    )

    assert result.exit_code == 0
    assert "RAW_UNADJUSTED" in result.output
    assert "NONE" in result.output
    assert "CLEAR" in result.output
