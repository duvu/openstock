from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.data_availability.models import (
    DataArtifact,
    EnsureDataAction,
    EnsureDataActionStatus,
    EnsureDataResult,
    EnsureDataStatus,
    EvidenceIssue,
    evidence_issue_artifact,
)
from vnalpha.data_availability.planner import (
    EnsureDataSnapshot,
    plan_data_availability,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_availability.raw_evidence import get_raw_ohlcv_window_evidence
from vnalpha.features.status import FEATURE_STATUS_CONTRACT_VERSION
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    create_ingestion_run,
    finish_ingestion_run,
    insert_raw_ohlcv,
)

_DATE = "2025-06-30"
_LINEAGE_FIELDS = frozenset(
    {
        "as_of_bar_date",
        "feature_build_version",
        "ingestion_run_id",
        "scoring_version",
        "selected_provider",
        "scoring_policy_id",
        "scoring_policy_version",
        "scoring_policy_hash",
        "scoring_policy_status",
    }
)


def _snapshot(**overrides: object) -> EnsureDataSnapshot:
    values: dict[str, object] = {
        "symbol": "FPT",
        "target_date": _DATE,
        "lookback_start": _DATE,
        "symbol_known": True,
        "canonical_bars": 1,
        "benchmark_bars": 1,
        "feature_snapshot_exists": True,
        "candidate_score_exists": True,
        "candidate_score_as_of_date": _DATE,
        "quality_status": "pass",
        "lineage_fields": _LINEAGE_FIELDS,
        "latest_canonical_bar_date": _DATE,
        "latest_benchmark_bar_date": _DATE,
        "feature_snapshot_row_exists": True,
        "feature_profile_acceptable": True,
        "feature_lineage_acceptable": True,
        "raw_ohlcv_bars": 1,
        "latest_raw_bar_date": _DATE,
    }
    values.update(overrides)
    return EnsureDataSnapshot(**values)


def _fresh_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()
    run_migrations(conn=conn)
    return conn


def _insert_symbol(conn: duckdb.DuckDBPyConnection, symbol: str) -> None:
    conn.execute(
        "INSERT INTO symbol_master (symbol, is_active) VALUES (?, TRUE)", [symbol]
    )


def _insert_canonical(
    conn: duckdb.DuckDBPyConnection, symbol: str, quality: str
) -> None:
    conn.execute(
        """
        INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume,
             selected_provider, quality_status, ingestion_run_id,
             source_service_run_id)
        VALUES (?, ?, '1D', 100, 110, 90, 105, 1000000,
                'fixture', ?, 'ingestion-fixture', 'service-fixture')
        """,
        [symbol, _DATE, quality],
    )


def _insert_raw(conn: duckdb.DuckDBPyConnection, symbol: str) -> None:
    run_id = create_ingestion_run(conn, "fixture", f"/fixture/{symbol.lower()}")
    insert_raw_ohlcv(
        conn,
        run_id,
        symbol,
        [
            {
                "time": _DATE,
                "interval": "1D",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1_000_000.0,
            }
        ],
        provider="fixture",
        quality_status="pass",
    )
    finish_ingestion_run(conn, run_id, status="SUCCESS")


def _insert_feature(conn: duckdb.DuckDBPyConnection, symbol: str) -> None:
    lineage = json.dumps(
        {
            "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
            "selected_provider": "fixture",
            "ingestion_run_id": "ingestion-fixture",
        }
    )
    conn.execute(
        """
        INSERT INTO feature_snapshot
            (symbol, date, close, ma20, as_of_bar_date, feature_data_status,
             feature_build_version, feature_generated_at, feature_profile,
             neutral_completeness, relative_strength_completeness,
             required_bar_count, observed_bar_count,
             feature_completeness_rule_version, lineage_json)
        VALUES (?, ?, 105.0, 100.0, ?, 'EXACT_DATE', 'fixture-v1',
                current_timestamp, 'STANDARD_120', 'COMPLETE', 'COMPLETE',
                1, 1, 'feature-completeness-v1', ?)
        """,
        [symbol, _DATE, _DATE, lineage],
    )
    conn.executemany(
        "INSERT INTO relative_strength_snapshot "
        "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
        "source_bar_date, benchmark_bar_date, source_row_count, "
        "benchmark_row_count, data_status, methodology_version, generated_at, "
        "lineage_json) VALUES (?, ?, 'VNINDEX', ?, 0.1, ?, ?, 1, 1, "
        "'SUCCESS', 'fixture-v1', current_timestamp, ?)",
        [[symbol, _DATE, horizon, _DATE, _DATE, lineage] for horizon in (20, 60)],
    )


def _insert_score(conn: duckdb.DuckDBPyConnection, symbol: str) -> None:
    policy = BASELINE_SCORING_POLICY
    lineage = json.dumps(
        {
            "as_of_bar_date": _DATE,
            "feature_build_version": "fixture-v1",
            "ingestion_run_id": "ingestion-fixture",
            "scoring_version": "fixture-v1",
            "selected_provider": "fixture",
            "scoring_policy_id": policy.policy_id,
            "scoring_policy_version": policy.version,
            "scoring_policy_hash": policy.payload_hash,
            "scoring_policy_status": policy.lifecycle_status.value,
        }
    )
    conn.execute(
        """
        INSERT INTO candidate_score
            (symbol, date, score, candidate_class, setup_type, trend_score,
             relative_strength_score, volume_score, base_score, breakout_score,
             risk_quality_score, evidence_json, risk_flags_json, lineage_json,
             scoring_policy_id, scoring_policy_version, scoring_policy_hash,
             scoring_policy_status)
        VALUES (?, ?, 0.75, 'STRONG_CANDIDATE', 'MOMENTUM_CONTINUATION',
                0.8, 0.7, 0.6, 0.5, 0.4, 0.9, '{}', '[]', ?, ?, ?, ?, ?)
        """,
        [
            symbol,
            _DATE,
            lineage,
            policy.policy_id,
            policy.version,
            policy.payload_hash,
            policy.lifecycle_status.value,
        ],
    )


def test_quality_issue_is_owned_by_canonical_ohlcv() -> None:
    assert (
        evidence_issue_artifact(EvidenceIssue.QUALITY_UNACCEPTABLE)
        is DataArtifact.CANONICAL_OHLCV
    )


def test_raw_window_counts_distinct_trading_sessions() -> None:
    conn = _fresh_conn()
    _insert_raw(conn, "FPT")
    _insert_raw(conn, "FPT")

    evidence = get_raw_ohlcv_window_evidence(conn, "FPT", _DATE, _DATE)

    assert evidence.row_count == 1


def test_partial_raw_window_requires_provider_sync_before_canonical_build() -> None:
    snapshot = _snapshot(canonical_bars=0, quality_status="unknown")

    plan = plan_data_availability(
        snapshot,
        DataAvailabilityPolicy(
            auto_sync=True,
            min_required_bars=2,
            require_benchmark_history=False,
        ),
    )

    assert plan.actions == (
        EnsureDataAction.OHLCV_SYNCED,
        EnsureDataAction.CANONICAL_BUILT,
    )


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"quality_status": "unknown"},
            (EnsureDataAction.CANONICAL_BUILT,),
        ),
        (
            {"unresolved_true_gap_count": 1},
            (EnsureDataAction.OHLCV_SYNCED, EnsureDataAction.CANONICAL_BUILT),
        ),
        (
            {
                "feature_snapshot_exists": False,
                "feature_snapshot_row_exists": True,
                "feature_lineage_acceptable": False,
            },
            (EnsureDataAction.FEATURES_BUILT,),
        ),
        (
            {
                "candidate_score_exists": False,
                "candidate_score_as_of_date": None,
                "lineage_fields": frozenset(),
            },
            (EnsureDataAction.SCORED,),
        ),
    ],
)
def test_typed_blocker_plans_only_the_next_repair_phase(
    overrides: dict[str, object],
    expected: tuple[EnsureDataAction, ...],
) -> None:
    snapshot = _snapshot(**overrides)
    plan = plan_data_availability(
        snapshot, DataAvailabilityPolicy(auto_sync=True, min_required_bars=1)
    )

    assert plan.actions == expected


def test_service_reloads_feature_evidence_before_scoring() -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    conn = _fresh_conn()
    for symbol in ("FPT", "VNINDEX"):
        _insert_symbol(conn, symbol)
        _insert_canonical(conn, symbol, "pass")
    score_calls: list[str] = []

    result = ensure_symbol_analysis_ready(
        conn,
        "FPT",
        _DATE,
        policy=DataAvailabilityPolicy(auto_sync=True, min_required_bars=1),
        _build_features_fn=lambda *_args, **_kwargs: {"built": 0, "skipped": 1},
        _score_universe_fn=lambda *_args, **_kwargs: score_calls.append("score") or 1,
    )

    assert score_calls == []
    assert EnsureDataAction.SCORED not in result.actions_taken
    assert result.status is EnsureDataStatus.PARTIAL
    assert _action_outcome_pair(result, EnsureDataAction.FEATURES_BUILT) == (
        EnsureDataAction.FEATURES_BUILT,
        EnsureDataActionStatus.FAILED,
    )
    assert (
        EvidenceIssue.FEATURE_SNAPSHOT_MISSING
        in next(
            item
            for item in result.artifact_evidence
            if item.artifact is DataArtifact.FEATURE_SNAPSHOT
        ).issues
    )


def _action_outcome_pair(
    result: EnsureDataResult, action: EnsureDataAction
) -> tuple[EnsureDataAction, EnsureDataActionStatus]:
    outcome = next(item for item in result.action_outcomes if item.action is action)
    return outcome.action, outcome.status


def test_force_refresh_rescores_after_rebuilding_features() -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    conn = _fresh_conn()
    for symbol in ("FPT", "VNINDEX"):
        _insert_symbol(conn, symbol)
        _insert_canonical(conn, symbol, "pass")
    _insert_raw(conn, "FPT")
    _insert_feature(conn, "FPT")
    _insert_score(conn, "FPT")
    score_calls: list[str] = []

    result = ensure_symbol_analysis_ready(
        conn,
        "FPT",
        _DATE,
        policy=DataAvailabilityPolicy(
            auto_sync=True,
            min_required_bars=1,
            require_benchmark_history=False,
        ),
        force_refresh=True,
        _sync_ohlcv_fn=lambda *_args, **_kwargs: {"inserted": 0},
        _build_canonical_fn=lambda *_args, **_kwargs: {
            "upserted": 0,
            "rejected": 0,
        },
        _build_features_fn=lambda *_args, **_kwargs: {"built": 1, "skipped": 0},
        _score_universe_fn=lambda *_args, **_kwargs: score_calls.append("score") or 1,
    )

    assert score_calls == ["score"]
    assert EnsureDataAction.SCORED in result.actions_taken
    assert result.status is EnsureDataStatus.READY


def test_zero_scored_rows_is_a_typed_failed_action() -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    conn = _fresh_conn()
    for symbol in ("FPT", "VNINDEX"):
        _insert_symbol(conn, symbol)
        _insert_canonical(conn, symbol, "pass")
    _insert_feature(conn, "FPT")

    result = ensure_symbol_analysis_ready(
        conn,
        "FPT",
        _DATE,
        policy=DataAvailabilityPolicy(auto_sync=True, min_required_bars=1),
        _score_universe_fn=lambda *_args, **_kwargs: 0,
    )

    assert EnsureDataAction.SCORED not in result.actions_taken
    assert [
        (outcome.action, outcome.status.value) for outcome in result.action_outcomes
    ] == [(EnsureDataAction.SCORED, "FAILED")]


@pytest.mark.parametrize("symbol", ["FPT", "VCB"])
def test_unknown_canonical_quality_repairs_from_raw_without_provider_sync(
    symbol: str,
) -> None:
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready
    from vnalpha.data_availability.models import EnsureDataStatus

    conn = _fresh_conn()
    for value in (symbol, "VNINDEX"):
        _insert_symbol(conn, value)
    _insert_canonical(conn, symbol, "unknown")
    _insert_canonical(conn, "VNINDEX", "pass")
    _insert_raw(conn, symbol)

    def build_canonical(conn: duckdb.DuckDBPyConnection, **_kwargs: object):
        conn.execute(
            "UPDATE canonical_ohlcv SET quality_status = 'pass' WHERE symbol = ?",
            [symbol],
        )
        return {"upserted": 1, "rejected": 0}

    def build_features(conn: duckdb.DuckDBPyConnection, **_kwargs: object):
        _insert_feature(conn, symbol)
        return {"built": 1, "skipped": 0}

    def score(conn: duckdb.DuckDBPyConnection, **_kwargs: object) -> int:
        _insert_score(conn, symbol)
        return 1

    result = ensure_symbol_analysis_ready(
        conn,
        symbol,
        _DATE,
        policy=DataAvailabilityPolicy(auto_sync=True, min_required_bars=1),
        _sync_ohlcv_fn=lambda *_args, **_kwargs: pytest.fail("provider sync called"),
        _build_canonical_fn=build_canonical,
        _build_features_fn=build_features,
        _score_universe_fn=score,
    )

    assert result.status is EnsureDataStatus.READY
    assert result.actions_taken == [
        EnsureDataAction.CANONICAL_BUILT,
        EnsureDataAction.FEATURES_BUILT,
        EnsureDataAction.SCORED,
    ]


def test_nonrepairable_quality_failure_reports_canonical_build_remediation() -> None:
    from vnalpha.data_availability.deep_readiness_models import (
        DeepAnalysisReadinessRequest,
    )
    from vnalpha.data_availability.deep_readiness_service import (
        DeepAnalysisReadinessService,
    )
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    conn = _fresh_conn()
    for symbol in ("FPT", "VNINDEX"):
        _insert_symbol(conn, symbol)
    _insert_canonical(conn, "FPT", "unknown")
    _insert_canonical(conn, "VNINDEX", "pass")
    _insert_raw(conn, "FPT")
    _insert_feature(conn, "FPT")
    _insert_score(conn, "FPT")
    ensure_result = ensure_symbol_analysis_ready(
        conn,
        "FPT",
        _DATE,
        policy=DataAvailabilityPolicy(auto_sync=True, min_required_bars=1),
        _build_canonical_fn=lambda *_args, **_kwargs: {"upserted": 0, "rejected": 1},
    )

    readiness = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: ensure_result
    ).ensure_ready(DeepAnalysisReadinessRequest(conn, "FPT", _DATE))
    canonical = next(
        artifact
        for artifact in readiness.artifacts
        if artifact.name == "canonical_ohlcv"
    )

    assert canonical.error_code == "QUALITY_UNACCEPTABLE"
    assert [step.command for step in canonical.remediation_steps] == [
        "vnalpha build canonical --symbol FPT"
    ]
    score = next(
        artifact
        for artifact in readiness.artifacts
        if artifact.name == "candidate_score"
    )
    assert score.error_code is None
