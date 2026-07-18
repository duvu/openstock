"""Issue #163 — automatic, explicit and traceable chat data provisioning.

These tests exercise the unified ``ensure_current_symbol_ready`` application
operation and its integration with the natural-language planner, the assistant
executor tool trace and the slash-command path. They are network-free: the
underlying ensure engine is either satisfied by pre-populated warehouse rows
(the reuse path) or replaced with a controlled fake (refresh / partial /
service-unavailable paths).
"""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.assistant.models import IntentResult
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.data_availability.deep_readiness_models import (
    ReadinessArtifact,
    ReadinessArtifactStatus,
    ReadinessResult,
    RemediationAction,
    RemediationStep,
)
from vnalpha.data_provisioning import ensure_current_symbol as ecs_module
from vnalpha.data_provisioning import ensure_current_symbol_ready
from vnalpha.data_provisioning.ensure_current_symbol import ProvisioningOutcome
from vnalpha.features.status import FEATURE_STATUS_CONTRACT_VERSION
from vnalpha.warehouse.migrations import run_migrations

# ---------------------------------------------------------------------------
# Readiness-service stub (network-free outcome mapping)
# ---------------------------------------------------------------------------


def _readiness(
    *,
    actions: tuple[str, ...],
    ready: bool = True,
    errors: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    correlation_id: str = "corr-stub",
) -> ReadinessResult:
    status = ReadinessArtifactStatus.READY if ready else ReadinessArtifactStatus.FAILED
    artifact = ReadinessArtifact(
        name="candidate_score",
        status=status,
        actions=actions,
        freshness="fresh" if ready else "missing",
        lineage=(),
        error=None if ready else (errors[0] if errors else "unavailable"),
        remediation=None,
    )
    return ReadinessResult(
        symbol="FPT",
        requested_date="2025-06-30",
        resolved_date="2025-06-30",
        artifacts=(artifact,),
        actions=actions,
        warnings=warnings,
        errors=() if ready else (errors or ("unavailable",)),
        correlation_id=correlation_id,
    )


def _patch_service(
    monkeypatch,
    readiness: ReadinessResult,
    calls: list[dict],
    *,
    exercise_ensure: bool = False,
):
    class _StubService:
        def __init__(self, *, ensure=None):
            self._ensure = ensure

        def ensure_ready(self, request):
            if exercise_ensure and self._ensure is not None:
                try:
                    self._ensure(request.conn, request.symbol, request.requested_date)
                except Exception:  # noqa: BLE001
                    pass
            calls.append({"symbol": request.symbol})
            return readiness

    monkeypatch.setattr(ecs_module, "DeepAnalysisReadinessService", _StubService)


# ---------------------------------------------------------------------------
# Warehouse fixtures (network-free reuse path)
# ---------------------------------------------------------------------------


def _fresh_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()
    run_migrations(conn=conn)
    return conn


def _insert_symbol(conn, symbol="FPT") -> None:
    conn.execute(
        "INSERT INTO symbol_master (symbol, is_active, last_seen_at) "
        "VALUES (?, TRUE, current_timestamp)",
        [symbol],
    )


def _insert_canonical_bars(conn, symbol, dates, interval="1D") -> None:
    for d in dates:
        conn.execute(
            """
            INSERT INTO canonical_ohlcv
            (symbol, time, interval, open, high, low, close, volume,
             selected_provider, quality_status)
            VALUES (?, ?, ?, 100, 110, 90, 105, 1000000, 'test', 'pass')
            """,
            [symbol, d, interval],
        )


def _insert_feature_snapshot(conn, symbol, date_str) -> None:
    lineage = json.dumps(
        {
            "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
            "benchmark_symbol": "VNINDEX",
            "selected_provider": "test",
            "ingestion_run_id": "test-run",
        }
    )
    conn.execute(
        """
        INSERT INTO feature_snapshot
        (symbol, date, close, ma20, as_of_bar_date, feature_data_status,
         feature_build_version, feature_generated_at, feature_profile,
         neutral_completeness, relative_strength_completeness,
         required_bar_count, observed_bar_count, feature_completeness_rule_version,
         lineage_json)
        VALUES (?, ?, 105.0, 100.0, ?, 'EXACT_DATE', 'dev', current_timestamp,
                'STANDARD_120', 'COMPLETE', 'COMPLETE', 120, 120,
                'feature-completeness-v1', ?)
        """,
        [symbol, date_str, date_str, lineage],
    )
    conn.executemany(
        "INSERT INTO relative_strength_snapshot "
        "(symbol, date, benchmark_symbol, horizon_sessions, relative_return, "
        "source_bar_date, benchmark_bar_date, source_row_count, "
        "benchmark_row_count, data_status, methodology_version, generated_at, "
        "lineage_json) VALUES (?, ?, 'VNINDEX', ?, 0.1, ?, ?, 120, 120, "
        "'SUCCESS', 'test-v1', current_timestamp, ?)",
        [
            [symbol, date_str, horizon, date_str, date_str, lineage]
            for horizon in (20, 60)
        ],
    )


def _insert_candidate_score(conn, symbol, date_str, as_of_bar_date=None) -> None:
    lineage = {
        "as_of_bar_date": as_of_bar_date or date_str,
        "scoring_version": "test-v1",
        "feature_build_version": "test-v1",
        "selected_provider": "test",
        "ingestion_run_id": "test-run",
        "source_quality_status": "pass",
        "lineage_status": "COMPLETE",
    }
    conn.execute(
        """
        INSERT INTO candidate_score
        (symbol, date, score, candidate_class, setup_type,
         trend_score, relative_strength_score, volume_score,
         base_score, breakout_score, risk_quality_score,
         evidence_json, risk_flags_json, lineage_json)
        VALUES (?, ?, 0.75, 'STRONG_CANDIDATE', 'MOMENTUM_CONTINUATION',
                0.8, 0.7, 0.6, 0.5, 0.4, 0.9, '{}', '[]', ?)
        """,
        [symbol, date_str, json.dumps(lineage)],
    )


def _ready_warehouse(date="2025-06-30") -> duckdb.DuckDBPyConnection:
    conn = _fresh_conn()
    _insert_symbol(conn, "FPT")
    _insert_symbol(conn, "VNINDEX")
    _insert_canonical_bars(conn, "FPT", [date])
    _insert_canonical_bars(conn, "VNINDEX", [date])
    _insert_feature_snapshot(conn, "FPT", date)
    _insert_candidate_score(conn, "FPT", date, as_of_bar_date=date)
    return conn


# ===========================================================================
# Reuse path — fresh persisted data is reused without provider calls
# ===========================================================================


def test_reuse_fresh_data_returns_reused(monkeypatch):
    calls: list[dict] = []
    _patch_service(monkeypatch, _readiness(actions=("CACHE_HIT",)), calls)
    conn = _fresh_conn()
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30")
    assert result.outcome is ProvisioningOutcome.REUSED
    assert result.is_ready
    assert result.reused_fresh_data is True
    assert result.refreshed is False
    assert any(action.action == "reuse_fresh" for action in result.actions)
    assert result.correlation_id
    conn.close()


def test_correlation_id_is_reused_when_supplied(monkeypatch):
    from vnalpha.observability.context import get_correlation_id

    calls: list[dict] = []
    _patch_service(
        monkeypatch,
        _readiness(actions=("CACHE_HIT",), correlation_id="turn-123"),
        calls,
        exercise_ensure=True,
    )
    conn = _fresh_conn()
    result = ensure_current_symbol_ready(
        conn, "FPT", "2025-06-30", correlation_id="turn-123"
    )
    assert result.correlation_id == "turn-123"
    assert get_correlation_id() == "turn-123"
    conn.close()


# ===========================================================================
# Explicit refresh — bounded incremental work, discloses actions
# ===========================================================================


def test_explicit_refresh_forces_bounded_work(monkeypatch):
    ensure_calls: list[dict] = []

    def _capture_force_refresh(conn, symbol, target_date, *, force_refresh=False):
        ensure_calls.append({"force_refresh": force_refresh})
        from vnalpha.data_availability.models import (
            EnsureDataResult,
            EnsureDataStatus,
        )

        return EnsureDataResult(
            symbol=symbol, target_date=target_date, status=EnsureDataStatus.READY
        )

    monkeypatch.setattr(
        ecs_module, "ensure_symbol_analysis_ready", _capture_force_refresh
    )
    calls: list[dict] = []
    _patch_service(
        monkeypatch,
        _readiness(
            actions=(
                "OHLCV_SYNCED",
                "CANONICAL_BUILT",
                "FEATURES_BUILT",
                "SCORED",
            )
        ),
        calls,
        exercise_ensure=True,
    )
    conn = _fresh_conn()
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30", refresh=True)

    assert ensure_calls and ensure_calls[0]["force_refresh"] is True
    assert result.outcome is ProvisioningOutcome.REFRESHED
    assert result.refreshed is True
    action_names = {action.action for action in result.actions}
    assert {"sync_ohlcv", "build_canonical", "build_features", "score_symbol"} <= (
        action_names
    )
    conn.close()


# ===========================================================================
# Partial failure / service unavailable — typed, not promoted to ready
# ===========================================================================


def test_partial_failure_reports_failed(monkeypatch):
    calls: list[dict] = []
    _patch_service(
        monkeypatch,
        _readiness(actions=("SYMBOLS_SYNCED",), ready=False, errors=("blocked",)),
        calls,
    )
    conn = _fresh_conn()
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30")

    assert result.outcome is ProvisioningOutcome.FAILED
    assert not result.is_ready
    assert result.errors
    conn.close()


def test_nullable_remediation_steps_fall_back_without_crashing(monkeypatch):
    readiness = _readiness(
        actions=(),
        ready=False,
        errors=("missing canonical data",),
    )
    artifact = readiness.artifacts[0]
    object.__setattr__(artifact, "remediation_steps", None)
    object.__setattr__(artifact, "remediation", "vnalpha data status FPT")
    calls: list[dict] = []
    _patch_service(monkeypatch, readiness, calls)

    conn = _fresh_conn()
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30")

    assert result.outcome is ProvisioningOutcome.FAILED
    assert result.remediation == ("vnalpha data status FPT",)
    conn.close()


def test_remediation_filters_empty_and_duplicate_commands(monkeypatch):
    step = RemediationStep(
        action=RemediationAction.SYNC_OHLCV,
        artifact="canonical_ohlcv",
        command_surface="CLI",
        command="vnalpha data sync-ohlcv --symbols FPT",
        description="Sync FPT bars.",
        required=True,
    )
    empty_step = RemediationStep(
        action=RemediationAction.BUILD_CANONICAL,
        artifact="canonical_ohlcv",
        command_surface="CLI",
        command="",
        description="No usable command.",
        required=True,
    )
    readiness = _readiness(
        actions=(),
        ready=False,
        errors=("missing canonical data",),
    )
    artifact = readiness.artifacts[0]
    object.__setattr__(artifact, "remediation_steps", (step, empty_step, step))
    object.__setattr__(artifact, "remediation", "ignored fallback")
    calls: list[dict] = []
    _patch_service(monkeypatch, readiness, calls)

    conn = _fresh_conn()
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30")

    assert result.remediation == ("vnalpha data sync-ohlcv --symbols FPT",)
    conn.close()


@pytest.mark.parametrize(
    "malformed_step",
    [None, "not-a-step", {"command": "untrusted mapping"}, object()],
)
def test_malformed_remediation_steps_fall_back_without_crashing(
    monkeypatch, malformed_step
):
    readiness = _readiness(
        actions=(),
        ready=False,
        errors=("missing canonical data",),
    )
    artifact = readiness.artifacts[0]
    object.__setattr__(artifact, "remediation_steps", (malformed_step,))
    object.__setattr__(artifact, "remediation", "vnalpha data status FPT")
    calls: list[dict] = []
    _patch_service(monkeypatch, readiness, calls)

    conn = _fresh_conn()
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30")

    assert result.outcome is ProvisioningOutcome.FAILED
    assert result.remediation == ("vnalpha data status FPT",)
    conn.close()


def test_remediation_rejects_oversized_commands_and_bounds_total_payload(
    monkeypatch,
):
    oversized = RemediationStep(
        action=RemediationAction.SYNC_OHLCV,
        artifact="canonical_ohlcv",
        command_surface="CLI",
        command="x" * 1_000_000,
        description="Malformed oversized provider command.",
        required=True,
    )
    readiness = _readiness(
        actions=(),
        ready=False,
        errors=("missing canonical data",),
    )
    artifact = readiness.artifacts[0]
    object.__setattr__(artifact, "remediation_steps", (oversized,))
    object.__setattr__(artifact, "remediation", "y" * 1_000_000)
    calls: list[dict] = []
    _patch_service(monkeypatch, readiness, calls)

    conn = _fresh_conn()
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30")

    assert result.outcome is ProvisioningOutcome.FAILED
    assert result.remediation == ()
    assert sum(len(item) for item in result.remediation) <= 2_048
    conn.close()


def test_service_unavailable_raises_are_contained(monkeypatch):
    def _raises(conn, symbol, target_date, *, force_refresh=False, **_kwargs):
        raise RuntimeError("vnstock-service unreachable")

    monkeypatch.setattr(ecs_module, "ensure_symbol_analysis_ready", _raises)
    conn = _fresh_conn()
    _insert_symbol(conn, "FPT")
    result = ensure_current_symbol_ready(conn, "FPT", "2025-06-30")

    # The readiness service contains the ensure exception into a typed failure.
    assert result.outcome is ProvisioningOutcome.FAILED
    assert not result.is_ready
    # Public error text does not leak the raw provider exception string.
    assert all("unreachable" not in error.lower() for error in result.errors)
    conn.close()


# ===========================================================================
# Planner integration — NL and slash share the same operation/tool
# ===========================================================================


def test_planner_fetch_data_emits_provisioning_step():
    plan = PlanBuilder().build(
        IntentResult(intent="fetch_data", confidence=1.0, entities={"symbol": "FPT"})
    )
    assert not plan.is_refusal()
    assert [step.tool_name for step in plan.steps] == ["data.ensure_current_symbol"]
    assert plan.steps[0].arguments["refresh"] is True


def test_planner_deep_analysis_prepends_provisioning_step():
    plan = PlanBuilder().build(
        IntentResult(
            intent="deep_analyze_symbol", confidence=1.0, entities={"symbol": "FPT"}
        )
    )
    assert [step.tool_name for step in plan.steps] == [
        "data.ensure_current_symbol",
        "analysis.deep_symbol",
    ]


def test_provisioning_tool_is_assistant_and_autonomous_eligible():
    from vnalpha.policy.assistant_policy import (
        ASSISTANT_TOOL_NAMES,
        AUTONOMOUS_PLAN_TOOL_NAMES,
    )

    assert "data.ensure_current_symbol" in ASSISTANT_TOOL_NAMES
    assert "data.ensure_current_symbol" in AUTONOMOUS_PLAN_TOOL_NAMES


def test_unrestricted_fetch_tool_remains_non_autonomous():
    from vnalpha.policy.assistant_policy import AUTONOMOUS_PLAN_TOOL_NAMES

    # The bounded provisioning tool is allowed; the unrestricted data.fetch is not.
    assert "data.fetch" not in AUTONOMOUS_PLAN_TOOL_NAMES


# ===========================================================================
# Executor tool trace — provisioning is recorded on-trace
# ===========================================================================


def test_executor_records_provisioning_tool_trace(monkeypatch):
    from vnalpha.assistant.executor import AssistantExecutor
    from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
    from vnalpha.warehouse.assistant_repo import create_assistant_session

    calls: list[dict] = []
    _patch_service(monkeypatch, _readiness(actions=("CACHE_HIT",)), calls)
    conn = _fresh_conn()
    session_id = create_assistant_session(
        conn, surface="test", user_prompt="update FPT"
    )
    executor = AssistantExecutor(conn, assistant_session_id=session_id)
    plan = AssistantPlan(
        intent="fetch_data",
        steps=[
            ToolPlanStep(
                step_id="step_1",
                tool_name="data.ensure_current_symbol",
                arguments={"symbol": "FPT", "date": "2025-06-30", "refresh": True},
                purpose="Refresh current-symbol data",
                required_permission="WRITE_DATA",
            )
        ],
    )
    executor.execute(plan)

    rows = conn.execute(
        "SELECT tool_name, status FROM tool_trace WHERE assistant_session_id = ?",
        [session_id],
    ).fetchall()
    assert rows == [("data.ensure_current_symbol", "SUCCESS")]
    conn.close()


def test_executor_fails_closed_when_provisioning_not_ready(monkeypatch):
    from vnalpha.assistant.errors import ToolExecutionError
    from vnalpha.assistant.executor import AssistantExecutor
    from vnalpha.assistant.models import AssistantPlan, ToolPlanStep
    from vnalpha.warehouse.assistant_repo import create_assistant_session

    calls: list[dict] = []
    _patch_service(
        monkeypatch,
        _readiness(actions=(), ready=False, errors=("nope",)),
        calls,
    )
    conn = _fresh_conn()
    session_id = create_assistant_session(
        conn, surface="test", user_prompt="analyze FPT"
    )
    events = []
    executor = AssistantExecutor(
        conn, assistant_session_id=session_id, on_trace_event=events.append
    )
    plan = AssistantPlan(
        intent="deep_analyze_symbol",
        steps=[
            ToolPlanStep(
                step_id="prov",
                tool_name="data.ensure_current_symbol",
                arguments={"symbol": "FPT", "date": "2025-06-30"},
                purpose="Provision",
                required_permission="WRITE_DATA",
            ),
            ToolPlanStep(
                step_id="analysis",
                tool_name="analysis.deep_symbol",
                arguments={"symbol": "FPT", "date": "2025-06-30"},
                purpose="Analyze",
                required_permission="READ_SCORE",
            ),
        ],
    )
    with pytest.raises(ToolExecutionError):
        executor.execute(plan)

    # analysis.deep_symbol must never have executed (fail-closed).
    tools = [
        row[0]
        for row in conn.execute(
            "SELECT tool_name FROM tool_trace WHERE assistant_session_id = ?",
            [session_id],
        ).fetchall()
    ]
    assert "analysis.deep_symbol" not in tools
    assert [event.status for event in events] == ["RUNNING", "FAILED"]
    rows = conn.execute(
        "SELECT tool_name, status FROM tool_trace WHERE assistant_session_id = ?",
        [session_id],
    ).fetchall()
    assert rows == [("data.ensure_current_symbol", "FAILED")]
    conn.close()
