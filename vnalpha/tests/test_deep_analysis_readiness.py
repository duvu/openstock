from __future__ import annotations

import duckdb

from vnalpha.assistant import executor as assistant_executor
from vnalpha.assistant.executor import AssistantExecutor
from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.data_availability.deep_readiness import (
    DeepAnalysisReadinessRequest,
    DeepAnalysisReadinessService,
    ReadinessArtifactStatus,
    ReadinessResult,
)
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.data_provisioning.ensure_current_symbol import (
    CurrentSymbolReadyResult,
    ProvisioningOutcome,
)
from vnalpha.tools.models import ToolOutput, ToolPermission, ToolSpec
from vnalpha.tools.registry import LocalToolRegistry
from vnalpha.warehouse.assistant_repo import create_assistant_session
from vnalpha.warehouse.migrations import run_migrations


def _blocked_provisioning(readiness: ReadinessResult) -> CurrentSymbolReadyResult:
    """Wrap a failed ReadinessResult as a FAILED provisioning result."""
    return CurrentSymbolReadyResult(
        symbol=readiness.symbol,
        outcome=ProvisioningOutcome.FAILED,
        correlation_id=readiness.correlation_id,
        requested_date=readiness.requested_date,
        resolved_date=readiness.resolved_date,
        actions=(),
        reused_fresh_data=False,
        refreshed=False,
        warnings=readiness.warnings,
        errors=readiness.errors,
        remediation=(),
        readiness=readiness,
    )


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

    calls: list[tuple[str, str]] = []
    registry = LocalToolRegistry()
    registry.register(
        ToolSpec(
            name="data.ensure_current_symbol",
            description="Controlled current-symbol provisioning",
            permission=ToolPermission.WRITE_DATA,
        ),
        lambda **kwargs: (
            calls.append(("data.ensure_current_symbol", kwargs["symbol"]))
            or ToolOutput(
                data={
                    "outcome": "REUSED",
                    "errors": [],
                    "remediation": [],
                    "correlation_id": kwargs["correlation_id"],
                }
            )
        ),
    )
    registry.register(
        ToolSpec(
            name="analysis.deep_symbol",
            description="Controlled deep analysis",
            permission=ToolPermission.READ_SCORE,
        ),
        lambda **kwargs: (
            calls.append(("analysis.deep_symbol", kwargs["symbol"]))
            or ToolOutput(data={"available": True, "symbol": kwargs["symbol"]})
        ),
    )
    monkeypatch.setattr(
        assistant_executor,
        "_build_tool_registry",
        lambda _conn: registry,
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

    assert calls == [
        ("data.ensure_current_symbol", "FPT"),
        ("analysis.deep_symbol", "FPT"),
    ]
    assert execution[plan.steps[1].step_id]["data"] == {
        "available": True,
        "symbol": "FPT",
    }
    conn.close()
