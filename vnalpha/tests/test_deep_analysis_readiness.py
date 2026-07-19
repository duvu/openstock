from __future__ import annotations

import shlex

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
    ContextRequirement,
    DeepAnalysisReadinessRequest,
    DeepAnalysisReadinessService,
    ReadinessArtifact,
    ReadinessArtifactStatus,
    ReadinessResult,
    RemediationAction,
    RemediationStep,
)
from vnalpha.data_availability.models import (
    ArtifactEvidence,
    DataArtifact,
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
    EvidenceIssue,
)
from vnalpha.data_availability.planner import (
    capture_availability_snapshot,
    compute_lookback_start,
)
from vnalpha.data_availability.policy import DEFAULT_POLICY
from vnalpha.data_provisioning.ensure_current_symbol import (
    CurrentSymbolReadyResult,
    ProvisioningOutcome,
)
from vnalpha.observability.context import get_correlation_id
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.tools.models import ToolOutput
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
    assert {artifact.status for artifact in result.artifacts if artifact.blocking} == {
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
    assert canonical.remediation == (
        "vnalpha sync ohlcv --symbols FPT "
        f"--start {compute_lookback_start('2026-07-10', DEFAULT_POLICY.lookback_days)} "
        "--end 2026-07-10"
    )


def test_readiness_reports_typed_artifact_evidence_and_ordered_legacy_repair() -> None:
    # Given: canonical data remains missing after the bounded ensure path.
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.PARTIAL,
            actions=[],
            canonical_bars=0,
            features=False,
            score=False,
        )
    )

    # When: deep-analysis readiness is rendered.
    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", "2026-07-10")
    )

    # Then: canonical evidence is artifact-specific and repair is executable today.
    canonical = next(
        artifact for artifact in result.artifacts if artifact.name == "canonical_ohlcv"
    )
    assert canonical.available is False
    assert canonical.row_count == 0
    assert [step.command for step in canonical.remediation_steps] == [
        (
            "vnalpha sync ohlcv --symbols FPT "
            f"--start {compute_lookback_start('2026-07-10', DEFAULT_POLICY.lookback_days)} "
            "--end 2026-07-10"
        ),
        "vnalpha build canonical --symbol FPT",
    ]


def test_readiness_renders_independent_typed_provenance_for_each_artifact() -> None:
    # Given: the ensure result carries warehouse evidence, not parsed warning text.
    result = _ensure_result(
        status=EnsureDataStatus.PARTIAL,
        actions=[],
        cache_rejection_reasons=[],
    )
    result.artifact_evidence = (
        ArtifactEvidence(
            artifact=DataArtifact.CANONICAL_OHLCV,
            available=True,
            row_count=120,
            observed_as_of_date="2026-07-10",
            quality_status="pass",
            provider="VCI",
            ingestion_run_id="ing-canonical",
            lineage_fields=frozenset({"source_service_run_id"}),
        ),
        ArtifactEvidence(
            artifact=DataArtifact.FEATURE_SNAPSHOT,
            available=True,
            observed_as_of_date="2026-07-10",
            row_count=120,
            quality_status="complete",
            provider="VCI",
            ingestion_run_id="ing-feature",
            generated_at="2026-07-10 15:30:00+07:00",
            methodology_version="features-v1",
            lineage_fields=frozenset({"ingestion_run_id", "selected_provider"}),
        ),
        ArtifactEvidence(
            artifact=DataArtifact.CANDIDATE_SCORE,
            available=True,
            observed_as_of_date="2026-07-10",
            row_count=1,
            quality_status="pass",
            provider="VCI",
            ingestion_run_id="ing-score",
            methodology_version="features-v1",
            lineage_fields=frozenset({"scoring_version"}),
            issues=(EvidenceIssue.QUALITY_UNACCEPTABLE,),
        ),
    )

    readiness = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: result
    ).ensure_ready(DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", "2026-07-10"))

    artifacts = {artifact.name: artifact for artifact in readiness.artifacts}
    canonical = artifacts["canonical_ohlcv"]
    feature = artifacts["feature_snapshot"]
    score = artifacts["candidate_score"]
    assert canonical.provider == "VCI"
    assert canonical.ingestion_run_id == "ing-canonical"
    assert feature.generated_at == "2026-07-10 15:30:00+07:00"
    assert feature.methodology_version == "features-v1"
    assert score.status is ReadinessArtifactStatus.FAILED
    assert score.error_code == "QUALITY_UNACCEPTABLE"


def test_snapshot_collects_per_artifact_provenance_from_the_warehouse() -> None:
    # Given: each core artifact is persisted with independent provenance fields.
    conn = duckdb.connect()
    run_migrations(conn=conn)
    conn.execute(
        """
        INSERT INTO symbol_master (symbol, exchange, name, sector, industry, last_seen_at)
        VALUES ('FPT', 'HOSE', 'FPT Corp', 'Technology', 'Software', current_timestamp)
        """
    )
    for symbol, run_id in (("FPT", "ing-fpt"), ("VNINDEX", "ing-index")):
        conn.execute(
            """
            INSERT INTO canonical_ohlcv (
                symbol, time, interval, close, selected_provider,
                quality_status, ingestion_run_id, source_service_run_id
            )
            SELECT ?, DATE '2026-03-13' + CAST(value AS INTEGER), '1D', 100.0,
                   'VCI', 'pass', ?, 'service-run'
            FROM range(120) AS days(value)
            """,
            [symbol, run_id],
        )
    lineage = (
        '{"as_of_bar_date":"2026-07-10","scoring_version":"score-v1",'
        '"feature_build_version":"features-v1","selected_provider":"VCI",'
        '"ingestion_run_id":"ing-fpt",'
        f'"scoring_policy_id":"{BASELINE_SCORING_POLICY.policy_id}",'
        f'"scoring_policy_version":"{BASELINE_SCORING_POLICY.version}",'
        f'"scoring_policy_hash":"{BASELINE_SCORING_POLICY.payload_hash}",'
        f'"scoring_policy_status":"{BASELINE_SCORING_POLICY.lifecycle_status.value}"}}'
    )
    conn.execute(
        """
        INSERT INTO feature_snapshot (
            symbol, date, as_of_bar_date, benchmark_as_of_bar_date, source_row_count,
            benchmark_row_count, feature_data_status,
            feature_build_version, feature_generated_at, lineage_json
        ) VALUES ('FPT', '2026-07-10', '2026-07-10', '2026-07-10', 120, 120, 'complete',
                  'features-v1', current_timestamp, ?)
        """,
        [lineage],
    )
    conn.execute(
        """
        INSERT INTO candidate_score (
            symbol, date, score, candidate_class, lineage_json,
            scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, scoring_policy_status
        ) VALUES ('FPT', '2026-07-10', 1.0, 'A', ?, ?, ?, ?, ?)
        """,
        [
            lineage,
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )

    snapshot = capture_availability_snapshot(conn, "FPT", "2026-07-10", DEFAULT_POLICY)

    evidence = {item.artifact: item for item in snapshot.artifact_evidence}
    symbol = evidence[DataArtifact.SYMBOL_MASTER]
    canonical = evidence[DataArtifact.CANONICAL_OHLCV]
    feature = evidence[DataArtifact.FEATURE_SNAPSHOT]
    score = evidence[DataArtifact.CANDIDATE_SCORE]
    assert canonical.provider == "VCI"
    assert canonical.ingestion_run_id == "ing-fpt"
    assert canonical.required_row_count == DEFAULT_POLICY.min_required_bars
    assert canonical.window_start_date == "2026-03-13"
    assert symbol.source_symbol == "FPT"
    assert dict(symbol.symbol_metadata)["exchange"] == "HOSE"
    assert feature.generated_at is not None
    assert feature.methodology_version == "features-v1"
    assert feature.benchmark_as_of_date == "2026-07-10"
    assert feature.benchmark_row_count == 120
    assert score.provider == "VCI"
    assert score.feature_build_version == "features-v1"
    assert score.scoring_version == "score-v1"
    assert score.issues == ()


def test_missing_symbol_retains_typed_snapshot_evidence(tmp_path) -> None:
    conn = duckdb.connect()
    run_migrations(conn=conn)
    from vnalpha.data_availability.ensure import ensure_symbol_analysis_ready

    readiness = DeepAnalysisReadinessService(
        ensure=lambda connection, symbol, target_date: ensure_symbol_analysis_ready(
            connection,
            symbol,
            target_date,
            policy=DEFAULT_POLICY.__class__(auto_sync=False),
            _lock_dir=tmp_path,
        )
    ).ensure_ready(DeepAnalysisReadinessRequest(conn, "MISSING", "2026-07-10"))

    artifacts = {artifact.name: artifact for artifact in readiness.artifacts}
    assert artifacts["symbol_master"].available is False
    assert artifacts["canonical_ohlcv"].row_count == 0
    assert artifacts["benchmark_ohlcv"].available is False
    assert artifacts["feature_snapshot"].freshness == "missing"
    assert all(
        artifact.error_code != "CORE_EVIDENCE_UNAVAILABLE"
        for artifact in readiness.artifacts
    )


def test_stale_score_evidence_renders_stale_freshness() -> None:
    conn = duckdb.connect()
    run_migrations(conn=conn)
    conn.execute(
        """
        INSERT INTO candidate_score (
            symbol, date, score, candidate_class, lineage_json,
            scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, scoring_policy_status
        ) VALUES ('FPT', '2026-07-10', 1.0, 'A', ?, ?, ?, ?, ?)
        """,
        [
            '{"as_of_bar_date":"2026-06-01"}',
            BASELINE_SCORING_POLICY.policy_id,
            BASELINE_SCORING_POLICY.version,
            BASELINE_SCORING_POLICY.payload_hash,
            BASELINE_SCORING_POLICY.lifecycle_status.value,
        ],
    )

    snapshot = capture_availability_snapshot(conn, "FPT", "2026-07-10", DEFAULT_POLICY)

    score = next(
        item
        for item in snapshot.artifact_evidence
        if item.artifact is DataArtifact.CANDIDATE_SCORE
    )
    assert score.freshness == "stale"
    assert EvidenceIssue.SCORE_STALE in score.issues


def test_readiness_audits_start_and_sets_correlation_before_ensure(monkeypatch) -> None:
    # Given: an audit sink and an ensure function that observes its invocation.
    events = []
    monkeypatch.setattr(
        "vnalpha.data_availability.deep_readiness_audit.log_audit",
        lambda event_type, summary, **kwargs: events.append(
            {"event_type": event_type, "summary": summary, **kwargs}
        ),
    )

    def ensure(_conn, _symbol, _date):
        assert events[0]["event_type"] == "DEEP_ANALYSIS_READINESS_STARTED"
        assert get_correlation_id() == events[0]["extra"]["correlation_id"]
        return _ensure_result(
            status=EnsureDataStatus.READY,
            actions=[EnsureDataAction.CACHE_HIT],
        )

    # When: readiness runs.
    result = DeepAnalysisReadinessService(ensure=ensure).ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", "2026-07-10")
    )

    # Then: the observed correlation is the result correlation.
    assert result.correlation_id == events[0]["extra"]["correlation_id"]


def test_readiness_resolves_current_market_session_before_ensure(monkeypatch) -> None:
    observed_dates: list[str] = []
    monkeypatch.setattr(
        "vnalpha.data_availability.deep_readiness_service.resolve_market_session_date",
        lambda _value: "2026-07-10",
        raising=False,
    )
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, date: (
            observed_dates.append(date)
            or _ensure_result(
                status=EnsureDataStatus.READY,
                actions=[EnsureDataAction.CACHE_HIT],
            )
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", None)
    )

    assert observed_dates == ["2026-07-10"]
    assert result.requested_date is None
    assert result.resolved_date == "2026-07-10"


def test_readiness_uses_market_date_when_the_warehouse_is_uninitialized() -> None:
    observed_dates: list[str] = []
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, date: (
            observed_dates.append(date)
            or _ensure_result(
                status=EnsureDataStatus.READY,
                actions=[EnsureDataAction.CACHE_HIT],
            )
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", None)
    )

    assert observed_dates == [result.resolved_date]
    assert len(result.resolved_date) == 10


def test_readiness_sanitizes_raw_action_failure_details() -> None:
    result = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.PARTIAL,
            actions=[],
            canonical_bars=0,
            features=False,
            score=False,
            warnings=["Canonical build failed: provider secret-token"],
        )
    ).ensure_ready(DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", "2026-07-10"))

    assert result.is_ready is False
    assert result.warnings == ("A readiness action failed during readiness.",)
    assert "secret-token" not in result.failure_summary()


def test_readiness_quotes_symbol_in_copyable_remediation_commands() -> None:
    symbol = "FPT; touch /tmp/not-executed"
    result = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.PARTIAL,
            actions=[],
            canonical_bars=0,
            features=False,
            score=False,
            symbol=symbol.upper(),
        )
    ).ensure_ready(DeepAnalysisReadinessRequest(duckdb.connect(), symbol, "2026-07-10"))

    canonical = next(
        artifact for artifact in result.artifacts if artifact.name == "canonical_ohlcv"
    )
    command = canonical.remediation_steps[0].command
    assert shlex.split(command)[4] == symbol.upper()
    assert "'FPT; TOUCH /TMP/NOT-EXECUTED'" in command


def test_readiness_converts_unexpected_ensure_failure_to_sanitized_result() -> None:
    # Given: the underlying ensure path raises an unexpected runtime error.
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: (_ for _ in ()).throw(
            RuntimeError("provider response included secret-token")
        )
    )

    # When: readiness runs.
    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", "2026-07-10")
    )

    # Then: deep analysis remains blocked without exposing the underlying message.
    assert result.is_ready is False
    assert result.failure_summary() == "Core data readiness could not be evaluated."


def test_assistant_requirement_parser_normalizes_strings_and_rejects_unknown() -> None:
    # Given: planner arguments arrive as user-shaped strings.
    # When: the executor parses each context requirement.
    optional = assistant_executor._requirement(" optional ")
    required = assistant_executor._requirement("required")
    unknown = assistant_executor._requirement("later")

    # Then: valid values are normalized and unknown values become a typed outcome.
    assert optional is ContextRequirement.OPTIONAL
    assert required is ContextRequirement.REQUIRED
    assert unknown is ContextRequirement.INVALID


def test_readiness_contains_optional_missing_data_separately() -> None:
    # Given: optional market context is unavailable while core data is ready.
    result = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: _ensure_result(
            status=EnsureDataStatus.READY,
            actions=[EnsureDataAction.CACHE_HIT],
        )
    ).ensure_ready(
        DeepAnalysisReadinessRequest(
            duckdb.connect(),
            "FPT",
            "2026-07-10",
            market_regime_requirement=ContextRequirement.OPTIONAL,
        )
    )

    # Then: optional data is disclosed without making the readiness gate fail.
    assert result.is_ready is True
    assert result.to_panel_dict()["optional_missing_data"] == ["market_regime_snapshot"]


def test_readiness_converts_date_resolution_failure_to_typed_result(
    monkeypatch,
) -> None:
    # Given: the warehouse date resolver cannot determine an effective date.
    monkeypatch.setattr(
        "vnalpha.data_availability.deep_readiness_service.resolve_market_session_date",
        lambda _value: (_ for _ in ()).throw(ValueError("bad date")),
    )

    # When: readiness is evaluated.
    result = DeepAnalysisReadinessService().ensure_ready(
        DeepAnalysisReadinessRequest(duckdb.connect(), "FPT", None)
    )

    # Then: the failure is public and sanitized instead of escaping.
    assert result.is_ready is False
    assert result.failure_summary() == "Deep-analysis date could not be resolved."


def test_assistant_error_renders_every_ordered_remediation_step(monkeypatch) -> None:
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
                remediation=None,
                remediation_steps=(
                    RemediationStep(
                        action=RemediationAction.SYNC_OHLCV,
                        artifact="canonical_ohlcv",
                        command_surface="cli",
                        command="vnalpha sync ohlcv --symbols FPT --start 2025-05-16 --end 2026-07-10",
                        description="Download the required symbol OHLCV window.",
                        required=True,
                    ),
                    RemediationStep(
                        action=RemediationAction.BUILD_CANONICAL,
                        artifact="canonical_ohlcv",
                        command_surface="cli",
                        command="vnalpha build canonical --symbol FPT",
                        description="Build canonical OHLCV from downloaded bars.",
                        required=True,
                    ),
                ),
            ),
        ),
        actions=(),
        warnings=(),
        errors=("Required canonical_ohlcv is unavailable.",),
        correlation_id="test-remediation",
    )
    monkeypatch.setattr(
        assistant_executor,
        "ensure_deep_analysis_ready",
        lambda _conn, _symbol, _date, **_kwargs: readiness,
    )
    step = ToolPlanStep(
        step_id="step_1",
        tool_name="analysis.deep_symbol",
        arguments={"symbol": "FPT", "date": "2026-07-10"},
        purpose="Read deep symbol research.",
        required_permission="READ_SCORE",
    )

    with pytest.raises(ToolExecutionError) as error:
        assistant_executor._ensure_data_for_step(duckdb.connect(), step)

    assert "Remediation: vnalpha sync ohlcv" in str(error.value)
    assert "vnalpha build canonical --symbol FPT" in str(error.value)


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
            core_evidence_evaluated=False,
            failure_code="LOCK_CONTENDED",
        )
    )

    result = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-10")
    )

    assert result.is_ready is False
    assert "lock_contended" in result.failure_summary()
    assert all(
        artifact.status is ReadinessArtifactStatus.FAILED
        for artifact in result.artifacts
        if artifact.blocking
    )
    assert all(
        artifact.status is ReadinessArtifactStatus.NOT_REQUESTED
        for artifact in result.artifacts
        if not artifact.blocking
    )


def test_readiness_attributes_quality_rejection_to_candidate_score() -> None:
    # Given: persisted score data exists, but its quality contract rejects it.
    conn = duckdb.connect()
    ensure_result = _ensure_result(
        status=EnsureDataStatus.PARTIAL,
        actions=[],
    )
    ensure_result.artifact_evidence = (
        ArtifactEvidence(
            artifact=DataArtifact.CANDIDATE_SCORE,
            available=True,
            observed_as_of_date="2026-07-10",
            quality_status="fail",
            issues=(EvidenceIssue.QUALITY_UNACCEPTABLE,),
        ),
    )
    service = DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: ensure_result
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
        "ensure_current_symbol_ready",
        lambda _conn, _symbol, _date, **_kwargs: _blocked_provisioning(readiness),
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
        lambda _conn, _symbol, _date, **_kwargs: readiness,
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


@pytest.mark.parametrize(
    ("handler", "command"),
    [
        (analyze_handler, "/analyze FPT --date today"),
        (research_plan_handler, "/research-plan FPT --date today"),
        (setup_evidence_handler, "/setup-evidence FPT --date today"),
    ],
)
def test_deep_slash_today_reaches_readiness_as_current_market_session(
    monkeypatch, handler, command
) -> None:
    # Given: generic command normalization would resolve today to a Sunday.
    observed_dates: list[str | None] = []
    monkeypatch.setattr(
        "vnalpha.commands.normalizers.resolve_date",
        lambda _value: "2026-07-19",
    )
    monkeypatch.setattr(
        "vnalpha.commands.handlers.research_workflow_common.resolve_market_session_date",
        lambda _value: "2026-07-17",
        raising=False,
    )

    def readiness_for(_conn, symbol, requested_date, **_kwargs):
        observed_dates.append(requested_date)
        return ReadinessResult(
            symbol=symbol,
            requested_date=requested_date,
            resolved_date=requested_date or "unresolved",
            artifacts=(),
            actions=(),
            warnings=(),
            errors=("Blocked after date capture.",),
            correlation_id="slash-today-date",
        )

    if handler is analyze_handler:
        monkeypatch.setattr(
            handler,
            "ensure_current_symbol_ready",
            lambda *args, **kwargs: _blocked_provisioning(
                readiness_for(*args, **kwargs)
            ),
        )
    else:
        monkeypatch.setattr(handler, "ensure_deep_analysis_ready", readiness_for)
    conn = duckdb.connect()
    run_migrations(conn=conn)

    # When: literal today enters through the real slash-command executor.
    result = CommandExecutor(conn, surface="tui").execute(command)

    # Then: readiness receives Friday rather than the generic Sunday value.
    assert result.status is CommandStatus.FAILED
    assert observed_dates == ["2026-07-17"]


@pytest.mark.parametrize(
    ("command", "expected_tool_names"),
    [
        ("/analyze FPT", ["analysis.deep_symbol"]),
        ("/research-plan FPT", ["scenario.generate_research_plan"]),
        (
            "/setup-evidence FPT",
            ["analysis.deep_symbol", "evidence.get_setup_history"],
        ),
    ],
)
def test_deep_slash_omitted_date_propagates_resolved_market_session(
    monkeypatch, command, expected_tool_names
) -> None:
    # Given: readiness resolves an omitted Sunday date to the preceding session.
    resolved_date = "2026-07-17"
    readiness = ReadinessResult(
        symbol="FPT",
        requested_date=None,
        resolved_date=resolved_date,
        artifacts=(),
        actions=(),
        warnings=(),
        errors=(),
        correlation_id="slash-omitted-date",
    )
    monkeypatch.setattr(
        analyze_handler,
        "ensure_current_symbol_ready",
        lambda _conn, _symbol, _date, **_kwargs: CurrentSymbolReadyResult(
            symbol="FPT",
            outcome=ProvisioningOutcome.READY,
            correlation_id=readiness.correlation_id,
            requested_date=None,
            resolved_date=resolved_date,
            actions=(),
            reused_fresh_data=False,
            refreshed=True,
            warnings=(),
            errors=(),
            readiness=readiness,
        ),
    )
    monkeypatch.setattr(
        research_plan_handler,
        "ensure_deep_analysis_ready",
        lambda _conn, _symbol, _date: readiness,
    )
    monkeypatch.setattr(
        setup_evidence_handler,
        "ensure_deep_analysis_ready",
        lambda _conn, _symbol, _date: readiness,
    )
    observed_calls: list[tuple[str, str | None]] = []

    def call_tool(_executor, name, **kwargs):
        observed_calls.append((name, kwargs.get("date")))
        if name == "analysis.deep_symbol":
            return ToolOutput(
                data={
                    "as_of_date": resolved_date,
                    "candidate": {"setup_type": "BREAKOUT"},
                }
            )
        return ToolOutput(data={"as_of_date": resolved_date})

    monkeypatch.setattr(
        "vnalpha.tools.executor.TracedLocalToolExecutor.call", call_tool
    )
    conn = duckdb.connect()
    run_migrations(conn=conn)

    # When: the real slash executor runs without a --date option.
    result = CommandExecutor(conn, surface="cli").execute(command)

    # Then: every downstream tool receives the exact readiness session, never None.
    assert result.status is not CommandStatus.FAILED
    assert [name for name, _date in observed_calls] == expected_tool_names
    assert {date for _name, date in observed_calls} == {resolved_date}


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
        "ensure_current_symbol_ready",
        lambda _conn, _symbol, _date, **_kwargs: _blocked_provisioning(readiness),
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
        "vnalpha.data_availability.deep_readiness_audit.log_audit",
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
        *["DEEP_ANALYSIS_READINESS_ARTIFACT"] * 8,
        "DEEP_ANALYSIS_READINESS_CACHE_HIT",
        "DEEP_ANALYSIS_READINESS_COMPLETED",
    ]
    assert events[-1]["extra"]["correlation_id"] == result.correlation_id
    assert "errors" not in events[-1]["extra"]


def test_readiness_emits_correlated_failure_audit(monkeypatch) -> None:
    events: list[dict[str, object]] = []
    monkeypatch.setattr(
        "vnalpha.data_availability.deep_readiness_audit.log_audit",
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
