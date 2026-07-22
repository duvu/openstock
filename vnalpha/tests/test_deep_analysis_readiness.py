from __future__ import annotations

import json

import duckdb

from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.data_availability import ensure as availability_ensure
from vnalpha.data_availability.deep_readiness import (
    DeepAnalysisReadinessRequest,
    DeepAnalysisReadinessService,
    ReadinessArtifactStatus,
)
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_provisioning import (
    ensure_current_symbol as current_symbol_provisioning,
)
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.migrations import run_migrations


def _ensure_result(
    *,
    status: EnsureDataStatus,
    actions: list[EnsureDataAction],
    symbol: str = "FPT",
    canonical_bars: int = 120,
    benchmark_bars: int = 120,
    features: bool = True,
    score: bool = True,
    warnings: list[str] | None = None,
    cache_rejection_reasons: list[str] | None = None,
    core_evidence_evaluated: bool = True,
    failure_code: str | None = None,
) -> EnsureDataResult:
    return EnsureDataResult(
        symbol=symbol,
        target_date="2026-07-10",
        status=status,
        actions_taken=actions,
        canonical_bars=canonical_bars,
        benchmark_bars=benchmark_bars,
        feature_snapshot_exists=features,
        candidate_score_exists=score,
        symbol_known=True,
        core_evidence_evaluated=core_evidence_evaluated,
        failure_code=failure_code,
        freshness="cache_hit",
        warnings=warnings or [],
        cache_rejection_reasons=cache_rejection_reasons or [],
    )


def _seed_cached_deep_analysis(conn: duckdb.DuckDBPyConnection) -> None:
    target_date = "2026-07-10"
    lineage = {
        "as_of_bar_date": target_date,
        "scoring_version": "v1",
        "scoring_policy_id": "baseline",
        "scoring_policy_version": "v1",
        "scoring_policy_hash": "fixture-hash",
        "scoring_policy_status": "APPROVED",
        "feature_build_version": "v1",
        "selected_provider": "fixture",
        "ingestion_run_id": "fixture-run",
        "benchmark_symbol": "VNINDEX",
        "feature_status_contract_version": "feature-data-status-v1",
    }
    conn.executemany(
        "INSERT INTO symbol_master (symbol, name, is_active) VALUES (?, ?, TRUE)",
        [("FPT", "FPT"), ("VNINDEX", "VNINDEX")],
    )
    conn.executemany(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, quality_status, "
        "ingestion_run_id, source_service_run_id) "
        "VALUES (?, ?, '1D', 100.0, 'fixture', 'pass', 'fixture-run', 'service-run')",
        [("FPT", target_date), ("VNINDEX", target_date)],
    )
    conn.execute(
        "INSERT INTO feature_snapshot "
        "(symbol, date, close, as_of_bar_date, benchmark_as_of_bar_date, "
        "source_row_count, benchmark_row_count, feature_data_status, "
        "feature_build_version, lineage_json, feature_profile, neutral_completeness, "
        "relative_strength_completeness) "
        "VALUES ('FPT', ?, 100.0, ?, ?, 1, 1, 'EXACT_DATE', 'v1', ?, "
        "'STANDARD_120', 'COMPLETE', 'COMPLETE')",
        [target_date, target_date, target_date, json.dumps(lineage)],
    )
    conn.executemany(
        "INSERT INTO relative_strength_snapshot "
        "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
        "source_bar_date, benchmark_bar_date, source_row_count, benchmark_row_count, "
        "data_status, methodology_version, lineage_json) "
        "VALUES ('FPT', ?, 'VNINDEX', ?, 0.1, ?, ?, 1, 1, 'SUCCESS', 'v1', ?) ",
        [
            (target_date, 20, target_date, target_date, json.dumps(lineage)),
            (target_date, 60, target_date, target_date, json.dumps(lineage)),
        ],
    )
    conn.execute(
        "INSERT INTO candidate_score "
        "(symbol, date, score, candidate_class, lineage_json, scoring_policy_id, "
        "scoring_policy_version, scoring_policy_hash, scoring_policy_status) "
        "VALUES ('FPT', ?, 0.75, 'WATCH_CANDIDATE', ?, 'baseline', 'v1', "
        "'fixture-hash', 'APPROVED')",
        [target_date, json.dumps(lineage)],
    )


def test_readiness_reports_actionable_core_status(monkeypatch) -> None:
    conn = duckdb.connect()
    run_migrations(conn=conn)
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.READY,
            actions=[EnsureDataAction.CACHE_HIT],
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10")
    )

    assert result.is_ready is True
    assert {artifact.status for artifact in result.artifacts if artifact.blocking} == {
        ReadinessArtifactStatus.READY
    }
    assert {
        artifact.status for artifact in result.artifacts if not artifact.blocking
    } == {ReadinessArtifactStatus.NOT_REQUESTED}
    assert result.actions == (EnsureDataAction.CACHE_HIT.value,)
    assert result.correlation_id

    failed_result = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: (_ for _ in ()).throw(RuntimeError())
    ).ensure_ready(DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10"))

    assert failed_result.is_ready is False
    assert failed_result.errors == (
        "Deep-analysis preparation failed at stage core_provisioning "
        "(dataset=core, symbol=FPT, effective_date=2026-07-10, "
        "category=ENSURE_EXCEPTION): RuntimeError",
    )

    unexplained_result = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.FAILED,
            actions=[],
        )
    ).ensure_ready(DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10"))

    assert unexplained_result.errors == (
        "Deep-analysis preparation failed without a stage diagnostic "
        "(symbol=FPT, effective_date=2026-07-10, status=FAILED, "
        "category=PROVISIONING_RESULT_INCONSISTENT): "
        "the provisioning result reported not-ready without error evidence",
    )

    _seed_cached_deep_analysis(conn)
    cache_policy = DataAvailabilityPolicy(
        min_required_bars=1,
        lookback_days=1,
    )

    def _ensure_cached_symbol(
        ensure_conn: duckdb.DuckDBPyConnection,
        symbol: str,
        target_date: str | None,
        *,
        force_refresh: bool = False,
    ):
        return availability_ensure.ensure_symbol_analysis_ready(
            ensure_conn,
            symbol,
            target_date,
            policy=cache_policy,
            force_refresh=force_refresh,
        )

    monkeypatch.setattr(
        current_symbol_provisioning,
        "ensure_symbol_analysis_ready",
        _ensure_cached_symbol,
    )
    plan = PlanBuilder().build(
        IntentResult(
            intent="deep_analyze_symbol",
            confidence=1.0,
            entities={"symbol": "FPT", "date": "2026-07-10"},
        )
    )
    session_id = create_assistant_session(
        conn,
        surface="test",
        user_prompt="phan tich co phieu FPT",
    )
    execution = AssistantExecutor(conn, assistant_session_id=session_id).execute(plan)

    assert [step.tool_name for step in plan.steps] == [
        "data.ensure_current_symbol",
        "analysis.deep_symbol",
    ]
    provisioning = execution[plan.steps[0].step_id]["data"]
    analysis = execution[plan.steps[1].step_id]["data"]
    assert provisioning["outcome"] == "REUSED"
    assert provisioning["reused_fresh_data"] is True
    assert analysis["symbol"] == "FPT"
    assert analysis["available"] is True
    assert analysis["as_of_date"] == "2026-07-10"
    assert analysis["candidate"]["score"] == 0.75
    assert analysis["missing_data"] == []
    conn.close()
