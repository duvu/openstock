from __future__ import annotations

from vnalpha.data_availability.deep_readiness import (
    ContextRequirement,
    ReadinessArtifact,
    ReadinessArtifactStatus,
    ReadinessResult,
)


def test_not_requested_context_does_not_block_ready_core_result() -> None:
    # Given: the core artifacts are ready and market context was not requested.
    result = ReadinessResult(
        symbol="FPT",
        requested_date="2026-07-10",
        resolved_date="2026-07-10",
        artifacts=(
            ReadinessArtifact(
                name="candidate_score",
                status=ReadinessArtifactStatus.READY,
                actions=(),
                freshness="exact",
                lineage=(),
                error=None,
                remediation=None,
                required=True,
                blocking=True,
            ),
            ReadinessArtifact(
                name="market_regime_snapshot",
                status=ReadinessArtifactStatus.NOT_REQUESTED,
                actions=(),
                freshness="not_requested",
                lineage=(),
                error=None,
                remediation=None,
                required=False,
                blocking=False,
                requirement=ContextRequirement.NOT_REQUESTED,
            ),
        ),
        actions=(),
        warnings=(),
        errors=(),
        correlation_id="context-not-requested",
    )

    # When: readiness determines whether analysis may proceed.
    ready = result.is_ready

    # Then: only the blocking core artifact controls the gate.
    assert ready is True


def _usable_market_snapshot():
    from datetime import date, datetime, timezone

    from vnalpha.research_intelligence.models import MarketRegimeSnapshot

    return MarketRegimeSnapshot(
        as_of_date=date(2026, 7, 10),
        benchmark_symbol="VNINDEX",
        benchmark_bar_date=date(2026, 7, 10),
        close=100.0,
        ma20=99.0,
        ma50=98.0,
        ma50_slope=1.0,
        return20=0.1,
        return60=0.2,
        volatility20=0.1,
        breadth_active_count=24,
        breadth_eligible_count=24,
        breadth_excluded_count=0,
        breadth_coverage=1.0,
        pct_above_ma20=1.0,
        pct_above_ma50=1.0,
        pct_positive_return20=1.0,
        regime="RISK_ON",
        trend="UPTREND",
        volatility="NORMAL",
        quality="COMPLETE",
        caveats=(),
        lineage={
            "input": "fixture",
            "exchange_coverage": 1.0,
            "liquidity_coverage": 1.0,
        },
        methodology_version="market-regime-v2",
        generated_at=datetime.now(timezone.utc),
    )
