from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import duckdb

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.models import (
    AssistantRequest,
    IntentResult,
    PreparedAssistantTurn,
    ToolPlanStep,
    plan_hash,
)
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.core.dates import resolve_market_session_date
from vnalpha.data_availability.deep_readiness import (
    DeepAnalysisReadinessRequest,
    DeepAnalysisReadinessService,
)
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.warehouse.assistant_repo import (
    create_assistant_session,
    mark_assistant_session_prepared,
    persist_prepared_turn,
)
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


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


def _seed_cached_deep_analysis(
    conn: duckdb.DuckDBPyConnection,
    target_date: str,
    *,
    symbol: str = "FPT",
    include_benchmark: bool = True,
) -> None:
    target_session = date.fromisoformat(target_date)
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
        "INSERT INTO symbol_master (symbol, name, is_active) VALUES (?, ?, TRUE) "
        "ON CONFLICT DO NOTHING",
        [
            (symbol, symbol),
            *((("VNINDEX", "VNINDEX"),) if include_benchmark else ()),
        ],
    )
    conn.executemany(
        "INSERT INTO canonical_ohlcv "
        "(symbol, time, interval, close, selected_provider, quality_status, "
        "ingestion_run_id, source_service_run_id) "
        "VALUES (?, ?, '1D', 100.0, 'fixture', 'pass', 'fixture-run', 'service-run') "
        "ON CONFLICT DO NOTHING",
        [
            (seed_symbol, (target_session - timedelta(days=offset)).isoformat())
            for seed_symbol in ((symbol, "VNINDEX") if include_benchmark else (symbol,))
            for offset in range(120)
        ],
    )
    conn.execute(
        "INSERT INTO feature_snapshot "
        "(symbol, date, close, as_of_bar_date, benchmark_as_of_bar_date, "
        "source_row_count, benchmark_row_count, feature_data_status, "
        "feature_build_version, lineage_json, feature_profile, neutral_completeness, "
        "relative_strength_completeness) "
        "VALUES (?, ?, 100.0, ?, ?, 120, 120, 'EXACT_DATE', 'v1', ?, "
        "'STANDARD_120', 'COMPLETE', 'COMPLETE')",
        [symbol, target_date, target_date, target_date, json.dumps(lineage)],
    )
    conn.executemany(
        "INSERT INTO relative_strength_snapshot "
        "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
        "source_bar_date, benchmark_bar_date, source_row_count, benchmark_row_count, "
        "data_status, methodology_version, lineage_json) "
        "VALUES (?, ?, 'VNINDEX', ?, 0.1, ?, ?, 1, 1, 'SUCCESS', 'v1', ?) ",
        [
            (symbol, target_date, 20, target_date, target_date, json.dumps(lineage)),
            (symbol, target_date, 60, target_date, target_date, json.dumps(lineage)),
        ],
    )
    conn.execute(
        "INSERT INTO candidate_score "
        "(symbol, date, score, candidate_class, lineage_json, scoring_policy_id, "
        "scoring_policy_version, scoring_policy_hash, scoring_policy_status) "
        "VALUES (?, ?, 0.75, 'WATCH_CANDIDATE', ?, 'baseline', 'v1', "
        "'fixture-hash', 'APPROVED')",
        [symbol, target_date, json.dumps(lineage)],
    )


def test_readiness_reports_actionable_core_status() -> None:
    conn = duckdb.connect()
    run_migrations(conn=conn)
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
    conn.close()


def test_live_deep_analysis_plan_reuses_fresh_evidence(tmp_path: Path) -> None:
    warehouse_path = tmp_path / "warehouse.duckdb"
    coordinator = WarehouseWriteCoordinator(path=warehouse_path)
    requested_date = resolve_market_session_date("today")
    latest_validated_date = (
        date.fromisoformat(requested_date) - timedelta(days=1)
    ).isoformat()
    plan = PlanBuilder().build(
        IntentResult(
            intent="deep_analyze_symbol",
            confidence=1.0,
            entities={"symbol": "FPT", "date": "today"},
        )
    )
    plan.steps.insert(
        1,
        ToolPlanStep(
            step_id="deep_hpg",
            tool_name="analysis.deep_symbol",
            arguments={"symbol": "HPG", "date": "today"},
            purpose="Analyze HPG using its requested session",
            required_permission="READ_WAREHOUSE",
        ),
    )
    request = AssistantRequest(
        current_user_prompt="phan tich co phieu FPT",
        date="today",
        date_is_implicit=True,
    )
    with coordinator.transaction() as conn:
        run_migrations(conn=conn)
        _seed_cached_deep_analysis(conn, latest_validated_date)
        _seed_cached_deep_analysis(
            conn,
            requested_date,
            symbol="HPG",
            include_benchmark=True,
        )
        session_id = create_assistant_session(
            conn,
            surface="test",
            user_prompt=request.current_user_prompt,
        )
        prepared = PreparedAssistantTurn(
            prepared_turn_id="prepared-deep-analysis",
            assistant_session_id=session_id,
            request=request,
            intent_result=IntentResult(
                intent="deep_analyze_symbol",
                confidence=1.0,
                entities={"symbol": "FPT", "date": "today"},
            ),
            plan=plan,
            plan_hash=plan_hash(plan),
            policy_status="PASS",
            created_at="2026-07-22T00:00:00+00:00",
        )
        persist_prepared_turn(conn, prepared)
        mark_assistant_session_prepared(
            conn,
            session_id,
            intent=prepared.intent_result.intent,
            plan=plan.to_dict(),
        )
    managed_app = AssistantApp.managed(
        surface="test",
        warehouse_path=warehouse_path,
        llm_client=LLMGatewayClient(
            LLMGatewayConfig(
                model="test-model",
                endpoint="http://127.0.0.1:1",
                timeout=1,
                max_output_tokens=1,
                max_retries=0,
                store_raw=False,
            )
        ),
    )
    answer, executed_plan = managed_app.execute_prepared(prepared)
    with coordinator.transaction() as conn:
        deep_traces = conn.execute(
            "SELECT input_json FROM tool_trace "
            "WHERE assistant_session_id = ? AND tool_name = 'analysis.deep_symbol' "
            "ORDER BY started_at",
            [session_id],
        ).fetchall()

    assert [step.tool_name for step in executed_plan.steps] == [
        "data.ensure_current_symbol",
        "analysis.deep_symbol",
        "analysis.deep_symbol",
    ]
    assert answer.summary
    assert [json.loads(trace[0])["date"] for trace in deep_traces] == [
        "today",
        latest_validated_date,
    ]
