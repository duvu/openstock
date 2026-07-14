from __future__ import annotations

import duckdb
import pytest

from vnalpha.assistant import executor as assistant_executor
from vnalpha.assistant.errors import ToolExecutionError
from vnalpha.assistant.models import ToolPlanStep
from vnalpha.commands.executor import CommandExecutor
from vnalpha.commands.handlers import analyze as analyze_handler
from vnalpha.commands.handlers import research_plan as research_plan_handler
from vnalpha.commands.handlers import setup_evidence as setup_evidence_handler
from vnalpha.commands.models import CommandStatus, ParsedCommand
from vnalpha.data_availability.deep_readiness import (
    DeepAnalysisReadinessRequest,
    DeepAnalysisReadinessService,
    ReadinessArtifact,
    ReadinessArtifactStatus,
    ReadinessResult,
)
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.warehouse.migrations import run_migrations


def _ensure_result(
    *,
    status: EnsureDataStatus,
    actions: list[EnsureDataAction],
    canonical_bars: int = 120,
    features: bool = True,
    score: bool = True,
    warnings: list[str] | None = None,
    cache_rejection_reasons: list[str] | None = None,
) -> EnsureDataResult:
    return EnsureDataResult(
        symbol="FPT",
        target_date="2026-07-10",
        status=status,
        actions_taken=actions,
        canonical_bars=canonical_bars,
        feature_snapshot_exists=features,
        candidate_score_exists=score,
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
    assert {artifact.status for artifact in result.artifacts} == {
        ReadinessArtifactStatus.READY
    }
    assert result.actions == (EnsureDataAction.CACHE_HIT.value,)
    assert result.correlation_id


def test_readiness_reports_bounded_provisioning_for_every_core_artifact() -> None:
    conn = duckdb.connect()
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.READY,
            actions=[
                EnsureDataAction.SYMBOLS_SYNCED,
                EnsureDataAction.OHLCV_SYNCED,
                EnsureDataAction.CANONICAL_BUILT,
                EnsureDataAction.BENCHMARK_SYNCED,
                EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
                EnsureDataAction.FEATURES_BUILT,
                EnsureDataAction.SCORED,
            ],
            cache_rejection_reasons=[
                "score_missing",
                "feature_snapshot_missing",
                "canonical_history_insufficient",
                "benchmark_history_insufficient",
                "quality_unacceptable",
                "lineage_incomplete",
            ],
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10")
    )

    assert result.is_ready is True
    assert {artifact.status for artifact in result.artifacts} == {
        ReadinessArtifactStatus.PROVISIONED
    }


def test_readiness_identifies_missing_core_artifact_and_remediation() -> None:
    # Given: canonical OHLCV remains unavailable after the bounded ensure path.
    conn = duckdb.connect()
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.PARTIAL,
            actions=[],
            canonical_bars=0,
            features=False,
            score=False,
            warnings=["Canonical build failed: provider unavailable"],
        )
    )

    # When: deep-analysis readiness is resolved.
    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10")
    )

    # Then: the required gate fails and names an actionable repair command.
    canonical = next(
        artifact for artifact in result.artifacts if artifact.name == "canonical_ohlcv"
    )
    assert result.is_ready is False
    assert canonical.status is ReadinessArtifactStatus.FAILED
    assert canonical.remediation == "vnalpha data download ohlcv FPT"


def test_readiness_fails_closed_during_ensure_lock_contention() -> None:
    conn = duckdb.connect()
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.PARTIAL,
            actions=[],
            canonical_bars=0,
            features=False,
            score=False,
            warnings=["Another ensure flow is active for FPT/2026-07-10. Skipping."],
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10")
    )

    assert result.is_ready is False
    assert "Another ensure flow is active" in result.failure_summary()
    assert all(
        artifact.status is ReadinessArtifactStatus.FAILED
        for artifact in result.artifacts
    )


def test_readiness_attributes_quality_rejection_to_candidate_score() -> None:
    # Given: persisted score data exists, but its quality contract rejects it.
    conn = duckdb.connect()
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.PARTIAL,
            actions=[],
            cache_rejection_reasons=["quality_unacceptable"],
        )
    )

    # When: deep-analysis readiness renders its per-artifact evidence.
    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10")
    )

    # Then: the actionable failure identifies the rejected score, not symbol master.
    symbol_master = next(
        artifact for artifact in result.artifacts if artifact.name == "symbol_master"
    )
    candidate_score = next(
        artifact for artifact in result.artifacts if artifact.name == "candidate_score"
    )
    assert symbol_master.status is ReadinessArtifactStatus.READY
    assert candidate_score.status is ReadinessArtifactStatus.FAILED
    assert (
        candidate_score.error
        == "Candidate score remains incomplete: quality_unacceptable."
    )
    assert result.failure_summary() == candidate_score.error


def test_analyze_returns_data_readiness_without_calling_deep_tool_when_blocked(
    monkeypatch,
) -> None:
    # Given: the readiness service has a failed required artifact.
    readiness = ReadinessResult(
        symbol="FPT",
        requested_date="2026-07-10",
        resolved_date="2026-07-10",
        artifacts=(
            ReadinessArtifact(
                name="candidate_score",
                status=ReadinessArtifactStatus.FAILED,
                actions=(),
                freshness="missing",
                lineage=(),
                error="Candidate score unavailable.",
                remediation="vnalpha data build score FPT --date 2026-07-10",
            ),
        ),
        actions=(),
        warnings=(),
        errors=("Candidate score unavailable.",),
        correlation_id="test-readiness",
    )
    monkeypatch.setattr(
        analyze_handler,
        "ensure_deep_analysis_ready",
        lambda _conn, _symbol, _date: readiness,
    )

    class ToolExecutor:
        def call(self, *_args, **_kwargs):
            raise AssertionError("analysis.deep_symbol must not execute")

    parsed = ParsedCommand(
        command_name="analyze",
        positional=["FPT"],
        filters=[],
        options={"date": "2026-07-10"},
        raw_text="/analyze FPT --date 2026-07-10",
    )

    # When: the user invokes the command path.
    result = analyze_handler.handle_analyze(
        parsed,
        conn=duckdb.connect(),
        tool_executor=ToolExecutor(),
    )

    # Then: the command surfaces deterministic readiness evidence only.
    assert result.status is CommandStatus.FAILED
    assert [panel.title for panel in result.panels] == ["Data Readiness"]
    assert result.panels[0].content["correlation_id"] == "test-readiness"


def test_assistant_preflight_blocks_deep_tool_after_failed_readiness(
    monkeypatch,
) -> None:
    readiness = ReadinessResult(
        symbol="FPT",
        requested_date="2026-07-10",
        resolved_date="2026-07-10",
        artifacts=(
            ReadinessArtifact(
                name="benchmark_ohlcv",
                status=ReadinessArtifactStatus.FAILED,
                actions=(),
                freshness="missing",
                lineage=(),
                error="Required benchmark_ohlcv is unavailable.",
                remediation="vnalpha data download index VNINDEX",
            ),
        ),
        actions=(),
        warnings=(),
        errors=("Required benchmark_ohlcv is unavailable.",),
        correlation_id="test-readiness",
    )
    monkeypatch.setattr(
        assistant_executor,
        "ensure_deep_analysis_ready",
        lambda _conn, _symbol, _date: readiness,
    )
    step = ToolPlanStep(
        step_id="step_1",
        tool_name="analysis.deep_symbol",
        arguments={"symbol": "FPT", "date": "2026-07-10"},
        purpose="Read deep symbol research.",
        required_permission="READ_SCORE",
    )

    with pytest.raises(ToolExecutionError, match="benchmark_ohlcv") as error:
        assistant_executor._ensure_data_for_step(duckdb.connect(), step)
    assert "Remediation: vnalpha data download index VNINDEX" in str(error.value)
    assert "correlation_id=test-readiness" in str(error.value)


def test_assistant_non_deep_preflight_keeps_best_effort_ensure(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnalpha.data_availability.ensure_symbol_analysis_ready",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )
    step = ToolPlanStep(
        step_id="step_1",
        tool_name="candidate.explain",
        arguments={"symbol": "FPT", "date": "2026-07-10"},
        purpose="Read persisted candidate evidence.",
        required_permission="READ_SCORE",
    )

    assistant_executor._ensure_data_for_step(duckdb.connect(), step)


@pytest.mark.parametrize(
    ("handler", "command"),
    [
        (research_plan_handler, "/research-plan FPT --date 2026-07-10"),
        (setup_evidence_handler, "/setup-evidence FPT --date 2026-07-10"),
    ],
)
def test_deep_command_paths_block_before_calling_the_deep_tool(
    monkeypatch, handler, command
) -> None:
    readiness = ReadinessResult(
        symbol="FPT",
        requested_date="2026-07-10",
        resolved_date="2026-07-10",
        artifacts=(
            ReadinessArtifact(
                name="canonical_ohlcv",
                status=ReadinessArtifactStatus.FAILED,
                actions=(),
                freshness="missing",
                lineage=(),
                error="Required canonical_ohlcv is unavailable.",
                remediation="vnalpha data download ohlcv FPT",
            ),
        ),
        actions=(),
        warnings=(),
        errors=("Required canonical_ohlcv is unavailable.",),
        correlation_id="command-readiness",
    )
    monkeypatch.setattr(
        handler,
        "ensure_deep_analysis_ready",
        lambda _conn, _symbol, _date: readiness,
    )

    class ToolExecutor:
        def call(self, *_args, **_kwargs):
            raise AssertionError("deep tool must not execute")

    conn = duckdb.connect()
    run_migrations(conn=conn)
    result = CommandExecutor(conn, surface="tui").execute(command)

    assert result.status is CommandStatus.FAILED
    assert [panel.title for panel in result.panels] == ["Data Readiness"]


def test_tui_command_path_renders_blocked_readiness_without_calling_tool(
    monkeypatch,
) -> None:
    readiness = ReadinessResult(
        symbol="FPT",
        requested_date="2026-07-10",
        resolved_date="2026-07-10",
        artifacts=(
            ReadinessArtifact(
                name="feature_snapshot",
                status=ReadinessArtifactStatus.FAILED,
                actions=(),
                freshness="missing",
                lineage=(),
                error="Required feature_snapshot is unavailable.",
                remediation="vnalpha data build features FPT --date 2026-07-10",
            ),
        ),
        actions=(),
        warnings=(),
        errors=("Required feature_snapshot is unavailable.",),
        correlation_id="tui-readiness",
    )
    monkeypatch.setattr(
        analyze_handler,
        "ensure_deep_analysis_ready",
        lambda _conn, _symbol, _date: readiness,
    )
    conn = duckdb.connect()
    run_migrations(conn=conn)

    result = CommandExecutor(conn, surface="tui").execute(
        "/analyze FPT --date 2026-07-10"
    )

    assert result.status is CommandStatus.FAILED
    assert [panel.title for panel in result.panels] == ["Data Readiness"]


def test_readiness_emits_correlated_audit_lifecycle(monkeypatch) -> None:
    events: list[dict[str, object]] = []
    monkeypatch.setattr(
        "vnalpha.data_availability.deep_readiness.log_audit",
        lambda event_type, summary, **kwargs: events.append(
            {"event_type": event_type, "summary": summary, **kwargs}
        ),
    )
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.READY,
            actions=[EnsureDataAction.CACHE_HIT],
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", "2026-07-10")
    )

    assert [event["event_type"] for event in events] == [
        "DEEP_ANALYSIS_READINESS_STARTED",
        "DEEP_ANALYSIS_READINESS_ARTIFACT",
        "DEEP_ANALYSIS_READINESS_ARTIFACT",
        "DEEP_ANALYSIS_READINESS_ARTIFACT",
        "DEEP_ANALYSIS_READINESS_ARTIFACT",
        "DEEP_ANALYSIS_READINESS_ARTIFACT",
        "DEEP_ANALYSIS_READINESS_CACHE_HIT",
        "DEEP_ANALYSIS_READINESS_COMPLETED",
    ]
    assert events[-1]["extra"]["correlation_id"] == result.correlation_id
    assert "errors" not in events[-1]["extra"]


def test_readiness_emits_correlated_failure_audit(monkeypatch) -> None:
    events: list[dict[str, object]] = []
    monkeypatch.setattr(
        "vnalpha.data_availability.deep_readiness.log_audit",
        lambda event_type, summary, **kwargs: events.append(
            {"event_type": event_type, "summary": summary, **kwargs}
        ),
    )
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.PARTIAL,
            actions=[],
            canonical_bars=0,
            features=False,
            score=False,
            warnings=["Canonical build failed: provider unavailable"],
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", "2026-07-10")
    )

    assert result.is_ready is False
    assert "DEEP_ANALYSIS_READINESS_PARTIAL" in {
        event["event_type"] for event in events
    }
    assert "DEEP_ANALYSIS_READINESS_FAILED" in {event["event_type"] for event in events}
    assert events[-1]["event_type"] == "DEEP_ANALYSIS_READINESS_COMPLETED"
    assert events[-1]["status"] == "FAILED"
    assert events[-1]["extra"]["correlation_id"] == result.correlation_id
