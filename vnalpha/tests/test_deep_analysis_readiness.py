from __future__ import annotations

import duckdb

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


def test_readiness_reports_cache_hit_for_every_required_core_artifact() -> None:
    # Given: the existing ensure service confirms a fresh core cache.
    conn = duckdb.connect()
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.READY,
            actions=[EnsureDataAction.CACHE_HIT],
        )
    )

    # When: deep-analysis readiness is resolved.
    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10")
    )

    # Then: each required artifact is ready without a provisioning action.
    assert result.is_ready is True
    assert {artifact.status for artifact in result.artifacts if artifact.blocking} == {
        ReadinessArtifactStatus.READY
    }
    assert {
        artifact.status for artifact in result.artifacts if not artifact.blocking
    } == {ReadinessArtifactStatus.NOT_REQUESTED}
    assert result.actions == (EnsureDataAction.CACHE_HIT.value,)
    assert result.correlation_id
