from __future__ import annotations

import duckdb
import pytest

from vnalpha.commands.models import CommandStatus, ParsedCommand
from vnalpha.data_availability.deep_context_readiness import (
    ContextReadinessInput,
    evaluate_context_readiness,
)
from vnalpha.data_availability.deep_readiness import (
    ContextRequirement,
    DeepAnalysisReadinessRequest,
    DeepAnalysisReadinessService,
    ReadinessArtifact,
    ReadinessArtifactStatus,
    ReadinessResult,
)
from vnalpha.data_availability.models import EnsureDataResult, EnsureDataStatus
from vnalpha.data_provisioning.ensure_current_symbol import (
    CurrentSymbolReadyResult,
    ProvisioningOutcome,
)
from vnalpha.tools.models import ToolOutput


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


def test_required_missing_market_context_is_built_and_revalidated(
    monkeypatch,
) -> None:
    # Given: the exact-date market snapshot is absent until the bounded builder runs.
    from vnalpha.data_availability import deep_context_readiness

    calls: list[str] = []
    snapshots = [None, _usable_market_snapshot()]
    monkeypatch.setattr(
        deep_context_readiness,
        "get_market_regime_as_of",
        lambda _conn, _date: snapshots.pop(0),
    )
    monkeypatch.setattr(
        deep_context_readiness,
        "get_latest_market_regime",
        lambda _conn: None,
    )
    monkeypatch.setattr(
        deep_context_readiness,
        "build_market_regime",
        lambda _conn, _date: calls.append("market_regime"),
    )

    # When: a required market context is evaluated.
    artifacts = evaluate_context_readiness(
        ContextReadinessInput(
            conn=None,
            symbol="FPT",
            resolved_date="2026-07-10",
            market_regime_requirement=ContextRequirement.REQUIRED,
            sector_strength_requirement=ContextRequirement.NOT_REQUESTED,
        )
    )

    # Then: readiness records the build only after reloading a usable snapshot.
    market = artifacts[0]
    assert calls == ["market_regime"]
    assert market.status is ReadinessArtifactStatus.PROVISIONED
    assert market.blocking is True
    assert market.error is None


def test_readiness_service_blocks_on_required_context_artifact(monkeypatch) -> None:
    # Given: core readiness succeeds but required market context remains unavailable.
    from vnalpha.data_availability import deep_readiness_service

    context_artifact = ReadinessArtifact(
        name="market_regime_snapshot",
        status=ReadinessArtifactStatus.FAILED,
        actions=(),
        freshness="unavailable",
        lineage=(),
        error="Required market regime context is unavailable.",
        remediation="vnalpha build market-regime --date 2026-07-10",
        requirement=ContextRequirement.REQUIRED,
        required=True,
        blocking=True,
    )
    observed_requirements: list[ContextRequirement] = []
    monkeypatch.setattr(
        deep_readiness_service,
        "evaluate_context_readiness",
        lambda context: (
            observed_requirements.append(context.market_regime_requirement)
            or (context_artifact,)
        ),
    )
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: EnsureDataResult(
            symbol="FPT",
            target_date="2026-07-10",
            status=EnsureDataStatus.READY,
            canonical_bars=120,
            benchmark_bars=120,
            feature_snapshot_exists=True,
            candidate_score_exists=True,
            symbol_known=True,
            core_evidence_evaluated=True,
        )
    )

    # When: the request explicitly requires market regime context.
    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(
            conn=None,
            symbol="FPT",
            requested_date="2026-07-10",
            market_regime_requirement=ContextRequirement.REQUIRED,
        )
    )

    # Then: the service passes the typed requirement through and fails closed.
    assert observed_requirements == [ContextRequirement.REQUIRED]
    assert result.is_ready is False
    assert result.failure_summary() == "Required market regime context is unavailable."


def test_analyze_flags_drive_readiness_and_deep_tool_requirements(monkeypatch) -> None:
    # Given: the command explicitly requests both supported context artifacts.
    from vnalpha.commands.handlers import analyze as analyze_handler

    observed_readiness: dict[str, ContextRequirement] = {}
    observed_tool: dict[str, ContextRequirement] = {}
    ready = ReadinessResult(
        symbol="FPT",
        requested_date="2026-07-10",
        resolved_date="2026-07-10",
        artifacts=(),
        actions=(),
        warnings=(),
        errors=(),
        correlation_id="analyze-context",
    )

    def ensure(
        _conn, _symbol, _date, *, market_regime_requirement, sector_strength_requirement
    ):
        observed_readiness["market"] = market_regime_requirement
        observed_readiness["sector"] = sector_strength_requirement
        return CurrentSymbolReadyResult(
            symbol="FPT",
            outcome=ProvisioningOutcome.READY,
            correlation_id="analyze-context",
            requested_date="2026-07-10",
            resolved_date="2026-07-10",
            actions=(),
            reused_fresh_data=False,
            refreshed=False,
            warnings=(),
            errors=(),
            readiness=ready,
        )

    class ToolExecutor:
        def call(self, _name, **kwargs):
            observed_tool["market"] = kwargs["market_regime_requirement"]
            observed_tool["sector"] = kwargs["sector_strength_requirement"]
            return ToolOutput(data={"as_of_date": "2026-07-10"})

    monkeypatch.setattr(analyze_handler, "ensure_current_symbol_ready", ensure)
    parsed = ParsedCommand(
        command_name="analyze",
        positional=["FPT"],
        filters=[],
        options={"date": "2026-07-10", "with-regime": True, "with-sector": True},
        raw_text="/analyze FPT --date 2026-07-10 --with-regime --with-sector",
    )

    # When: the command executes its preflight and read-tool call.
    result = analyze_handler.handle_analyze(
        parsed, conn=duckdb.connect(), tool_executor=ToolExecutor()
    )

    # Then: both phases receive the same explicit typed requirements.
    assert result.status is not CommandStatus.FAILED
    assert observed_readiness == {
        "market": ContextRequirement.REQUIRED,
        "sector": ContextRequirement.REQUIRED,
    }
    assert observed_tool == observed_readiness


@pytest.mark.parametrize(
    "warning",
    [
        "canonical failed: provider secret-token",
        "canonical Failed: provider secret-token",
        "canonical FAILED: provider secret-token",
        "canonical failure: provider secret-token",
        "canonical provider error: secret-token",
    ],
)
def test_readiness_sanitizes_context_warning_variants(warning: str) -> None:
    # Given: a lower-layer readiness warning carries a sensitive implementation detail.
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: EnsureDataResult(
            symbol="FPT",
            target_date="2026-07-10",
            status=EnsureDataStatus.PARTIAL,
            warnings=[warning],
            canonical_bars=0,
            benchmark_bars=0,
            symbol_known=False,
            core_evidence_evaluated=False,
        )
    )

    # When: the readiness result is rendered for a user.
    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(None, "FPT", "2026-07-10")
    )

    # Then: warning wording cannot leak the sensitive lower-layer detail.
    assert result.warnings == ("A readiness action failed during readiness.",)
    assert "secret-token" not in result.failure_summary()


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
