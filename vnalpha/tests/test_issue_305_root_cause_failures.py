"""Tests for issue #305: preserve root-cause failures in current-symbol prep.

The current-symbol readiness path must return truthful, structured, actionable
failure information — the failed stage, dataset, symbol, stable failure
category and sanitized root cause — instead of flattening every failure into a
generic "could not be made ready" wrapper.
"""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.data_availability.deep_readiness_models import (
    DeepAnalysisReadinessRequest,
)
from vnalpha.data_availability.deep_readiness_service import (
    DeepAnalysisReadinessService,
    _first_actionable_failure,
)
from vnalpha.data_availability.failure_classification import (
    classify_failure,
    dataset_for_action,
    sanitize_root_cause,
    subject_symbol,
)
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataActionOutcome,
    EnsureDataActionStatus,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _failed_result(**outcome_kwargs) -> EnsureDataResult:
    result = EnsureDataResult(
        symbol="FPT", target_date="2026-07-17", status=EnsureDataStatus.FAILED
    )
    result.action_outcomes.append(
        EnsureDataActionOutcome(
            status=EnsureDataActionStatus.FAILED,
            **outcome_kwargs,
        )
    )
    return result


# --- classification unit coverage -----------------------------------------


def test_classify_failure_maps_stable_categories() -> None:
    assert (
        classify_failure(
            EnsureDataAction.BENCHMARK_SYNCED, ValueError("no raw index rows")
        )
        == "NO_RAW_ROWS"
    )
    assert (
        classify_failure(
            EnsureDataAction.BENCHMARK_SYNCED,
            ValueError("provider does not support index acquisition"),
        )
        == "PROVIDER_UNSUPPORTED_DATASET"
    )
    assert (
        classify_failure(
            EnsureDataAction.CANONICAL_BUILT, ValueError("schema validation failed")
        )
        == "CANONICAL_SCHEMA_INVALID"
    )
    assert (
        classify_failure(
            EnsureDataAction.FEATURES_BUILT, ValueError("insufficient lookback window")
        )
        == "INSUFFICIENT_LOOKBACK"
    )
    assert (
        classify_failure(
            EnsureDataAction.SCORED, RuntimeError("scoring produced no row")
        )
        == "SCORE_INPUT_MISSING"
    )


def test_dataset_and_subject_symbol_are_stage_specific() -> None:
    assert dataset_for_action(EnsureDataAction.BENCHMARK_SYNCED) == "index.ohlcv"
    assert dataset_for_action(EnsureDataAction.OHLCV_SYNCED) == "equity.ohlcv"
    # Benchmark stages concern VNINDEX, not the requested symbol.
    assert (
        subject_symbol(EnsureDataAction.BENCHMARK_SYNCED, "FPT", "VNINDEX") == "VNINDEX"
    )
    assert subject_symbol(EnsureDataAction.OHLCV_SYNCED, "FPT", "VNINDEX") == "FPT"


def test_sanitize_root_cause_is_bounded_and_single_line() -> None:
    err = ValueError("line one\nline two " + "x" * 500)
    sanitized = sanitize_root_cause(err)
    assert "\n" not in sanitized
    assert sanitized.startswith("ValueError:")
    assert len(sanitized) <= 260


# --- readiness surface integration -----------------------------------------


def test_missing_index_raw_reports_benchmark_stage_failed(conn) -> None:
    def fake_ensure(_c, symbol, date):
        return _failed_result(
            action=EnsureDataAction.BENCHMARK_SYNCED,
            dataset="index.ohlcv",
            symbol="VNINDEX",
            failure_category="NO_RAW_ROWS",
            root_cause="ValueError: no raw index rows were available",
        )

    service = DeepAnalysisReadinessService(ensure=fake_ensure)
    readiness = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-17")
    )
    assert not readiness.is_ready
    joined = " ".join(readiness.errors)
    # The failed stage, dataset, symbol and sanitized cause are preserved.
    assert "BENCHMARK_SYNCED" in joined
    assert "index.ohlcv" in joined
    assert "VNINDEX" in joined
    assert "no raw index rows" in joined
    # Not the flattened generic wrapper.
    assert "could not be made ready" not in joined


def test_canonical_build_error_preserves_root_cause(conn) -> None:
    def fake_ensure(_c, symbol, date):
        return _failed_result(
            action=EnsureDataAction.CANONICAL_BUILT,
            dataset="equity.canonical_ohlcv",
            symbol="FPT",
            failure_category="CANONICAL_SCHEMA_INVALID",
            root_cause="ValueError: canonical schema validation failed",
        )

    service = DeepAnalysisReadinessService(ensure=fake_ensure)
    readiness = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-17")
    )
    joined = " ".join(readiness.errors)
    assert "CANONICAL_SCHEMA_INVALID" in joined
    assert "schema validation failed" in joined
    assert "could not be made ready" not in joined


def test_score_failure_identifies_missing_feature_input(conn) -> None:
    def fake_ensure(_c, symbol, date):
        return _failed_result(
            action=EnsureDataAction.SCORED,
            dataset="candidate_score",
            symbol="FPT",
            failure_category="SCORE_INPUT_MISSING",
            root_cause="RuntimeError: scoring produced no row for the requested symbol",
        )

    service = DeepAnalysisReadinessService(ensure=fake_ensure)
    readiness = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-17")
    )
    joined = " ".join(readiness.errors)
    assert "SCORE_INPUT_MISSING" in joined
    assert "SCORED" in joined


def test_first_actionable_failure_returns_first_failed_stage() -> None:
    result = EnsureDataResult(
        symbol="FPT", target_date="2026-07-17", status=EnsureDataStatus.PARTIAL
    )
    result.action_outcomes.extend(
        [
            EnsureDataActionOutcome(
                action=EnsureDataAction.OHLCV_SYNCED,
                status=EnsureDataActionStatus.SUCCESS,
            ),
            EnsureDataActionOutcome(
                action=EnsureDataAction.CANONICAL_BUILT,
                status=EnsureDataActionStatus.FAILED,
                dataset="equity.canonical_ohlcv",
                symbol="FPT",
                failure_category="CANONICAL_SCHEMA_INVALID",
                root_cause="ValueError: bad schema",
            ),
            EnsureDataActionOutcome(
                action=EnsureDataAction.SCORED,
                status=EnsureDataActionStatus.FAILED,
                dataset="candidate_score",
                symbol="FPT",
                failure_category="SCORE_INPUT_MISSING",
                root_cause="RuntimeError: no row",
            ),
        ]
    )
    summary = _first_actionable_failure(result)
    assert summary is not None
    # The FIRST failed stage wins, not a later one.
    assert "CANONICAL_BUILT" in summary
    assert "SCORED" not in summary


def test_no_failure_returns_none() -> None:
    result = EnsureDataResult(
        symbol="FPT", target_date="2026-07-17", status=EnsureDataStatus.READY
    )
    result.action_outcomes.append(
        EnsureDataActionOutcome(
            action=EnsureDataAction.OHLCV_SYNCED,
            status=EnsureDataActionStatus.SUCCESS,
        )
    )
    assert _first_actionable_failure(result) is None


def test_readiness_reports_requested_and_effective_date(conn) -> None:
    # Requesting "today" before EOD resolves to the latest completed session.
    def fake_ensure(_c, symbol, date):
        return _failed_result(
            action=EnsureDataAction.OHLCV_SYNCED,
            dataset="equity.ohlcv",
            symbol="FPT",
            failure_category="NO_RAW_ROWS",
            root_cause="ValueError: no rows",
        )

    service = DeepAnalysisReadinessService(ensure=fake_ensure)
    readiness = service.ensure_ready(
        DeepAnalysisReadinessRequest(conn, "FPT", "2026-07-17")
    )
    assert readiness.requested_date == "2026-07-17"
    # The effective/resolved trading date is exposed and correlation-searchable.
    assert readiness.resolved_date
    assert readiness.correlation_id


def test_structured_outcome_is_json_serializable() -> None:
    outcome = EnsureDataActionOutcome(
        action=EnsureDataAction.BENCHMARK_SYNCED,
        status=EnsureDataActionStatus.FAILED,
        dataset="index.ohlcv",
        symbol="VNINDEX",
        failure_category="NO_RAW_ROWS",
        root_cause="ValueError: no raw rows",
        elapsed_ms=12.5,
    )
    payload = outcome.to_dict()
    assert payload["action"] == "BENCHMARK_SYNCED"
    assert payload["status"] == "FAILED"
    assert payload["dataset"] == "index.ohlcv"
    assert payload["failure_category"] == "NO_RAW_ROWS"
    assert payload["elapsed_ms"] == 12.5

    # Success outcomes omit the failure fields.
    success = EnsureDataActionOutcome(
        action=EnsureDataAction.OHLCV_SYNCED,
        status=EnsureDataActionStatus.SUCCESS,
    )
    assert "failure_category" not in success.to_dict()


def test_provisioning_action_carries_failure_detail_to_trace(conn, monkeypatch) -> None:
    # The unified provisioning operation surfaces the failed stage detail on its
    # trace so CLI/TUI/tool callers render the actual failed stage (#305).
    from vnalpha.data_provisioning import ensure_current_symbol as ecs

    def fake_ensure(_c, symbol, date, **kwargs):
        return _failed_result(
            action=EnsureDataAction.BENCHMARK_SYNCED,
            dataset="index.ohlcv",
            symbol="VNINDEX",
            failure_category="NO_RAW_ROWS",
            root_cause="ValueError: no raw index rows were available",
        )

    monkeypatch.setattr(ecs, "ensure_symbol_analysis_ready", fake_ensure)

    result = ecs.ensure_current_symbol_ready(conn, "FPT", "2026-07-17")
    assert not result.is_ready
    failed_actions = [
        a for a in result.actions if a.status == "FAILED" and a.failure_category
    ]
    assert failed_actions
    action = failed_actions[0]
    assert action.failure_category == "NO_RAW_ROWS"
    assert action.dataset == "index.ohlcv"
    assert action.symbol == "VNINDEX"
    assert "no raw index rows" in (action.root_cause or "")
    # The trace dict carries the structured failed-stage detail.
    trace = result.to_trace_dict()
    failed_trace = [a for a in trace["actions"] if a["status"] == "FAILED"]
    assert failed_trace and failed_trace[0]["failure_category"] == "NO_RAW_ROWS"
