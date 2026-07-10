"""Integration tests: data-availability ensure wired into explain/compare handlers and NL path.

Tasks: 6.7-6.9 (explain handler), 7.6-7.7 (compare handler), 8.6-8.7 (NL path).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import duckdb
import pytest

from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import save_candidate_score


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


@pytest.fixture
def conn_scored(conn):
    today = date.today().isoformat()
    for sym in ("FPT", "HPG"):
        save_candidate_score(
            conn,
            sym,
            today,
            {
                "score": 0.75,
                "candidate_class": "STRONG_CANDIDATE",
                "setup_type": "MOMENTUM_CONTINUATION",
                "trend_score": 0.8,
                "relative_strength_score": 0.7,
                "volume_score": 0.6,
                "base_score": 0.5,
                "breakout_score": 0.4,
                "risk_quality_score": 0.9,
                "evidence_json": {"trend": "up"},
                "risk_flags_json": [],
                "lineage_json": {"scoring_version": "test", "as_of_bar_date": today},
                "data_quality_status": "pass",
            },
        )
    return conn, today


@pytest.fixture
def reg():
    return build_default_registry()


def _make_tool_executor(conn):
    registry = build_local_tool_registry(conn)
    return TracedLocalToolExecutor(conn, registry, session_id="test-session")


def _make_ready_result(symbol, target_date):
    return EnsureDataResult(
        symbol=symbol,
        target_date=target_date,
        status=EnsureDataStatus.READY,
        actions_taken=[EnsureDataAction.CACHE_HIT],
        canonical_bars=200,
        feature_snapshot_exists=True,
        candidate_score_exists=True,
    )


def _make_partial_result(symbol, target_date, warnings=None):
    return EnsureDataResult(
        symbol=symbol,
        target_date=target_date,
        status=EnsureDataStatus.PARTIAL,
        actions_taken=[EnsureDataAction.SYMBOLS_SYNCED, EnsureDataAction.OHLCV_SYNCED],
        canonical_bars=50,
        feature_snapshot_exists=False,
        candidate_score_exists=False,
        warnings=warnings or ["Insufficient canonical bars: 50 < 120 required."],
    )


def _make_failed_result(symbol, target_date):
    return EnsureDataResult(
        symbol=symbol,
        target_date=target_date,
        status=EnsureDataStatus.FAILED,
        errors=[f"Symbol '{symbol}' not found in symbol_master."],
    )


class TestExplainEnsureIntegration:
    """Tasks 6.7-6.9: ensure triggered inside /explain handler."""

    def test_missing_score_triggers_ensure(self, conn, reg):
        """6.7: explain for unknown symbol triggers ensure (which may fail gracefully)."""
        parsed = parse("/explain ZZZZ --date 2025-06-30")
        result = reg.execute(
            parsed, conn=conn, registry=reg, tool_executor=_make_tool_executor(conn)
        )
        assert result.status == "EMPTY_RESULT"
        assert result.summary is not None

    def test_explain_shows_data_readiness_panel_on_cache_hit(self, conn_scored, reg):
        """6.8: ensure returns READY → Data Readiness panel present."""
        conn, today = conn_scored
        with patch(
            "vnalpha.data_availability.ensure_symbol_analysis_ready",
            return_value=_make_ready_result("FPT", today),
        ):
            parsed = parse(f"/explain FPT --date {today}")
            result = reg.execute(
                parsed, conn=conn, registry=reg, tool_executor=_make_tool_executor(conn)
            )
        assert result.status == "SUCCESS"
        panel_titles = [p.title for p in result.panels]
        assert "Data Readiness" in panel_titles
        readiness_panel = next(p for p in result.panels if p.title == "Data Readiness")
        assert readiness_panel.content["status"] == "READY"

    def test_explain_ensure_failure_still_returns_result(self, conn_scored, reg):
        """6.9: ensure raises → handler still returns explain result without crash."""
        conn, today = conn_scored
        with patch(
            "vnalpha.data_availability.ensure_symbol_analysis_ready",
            side_effect=RuntimeError("service unavailable"),
        ):
            parsed = parse(f"/explain FPT --date {today}")
            result = reg.execute(
                parsed, conn=conn, registry=reg, tool_executor=_make_tool_executor(conn)
            )
        assert result.status == "SUCCESS"
        panel_titles = [p.title for p in result.panels]
        assert "Data Readiness" not in panel_titles


class TestCompareEnsureIntegration:
    """Tasks 7.6-7.7: ensure triggered inside /compare handler, Data Readiness propagation."""

    def test_compare_includes_ensure_warnings(self, conn_scored, reg):
        """7.6: ensure returns PARTIAL → warnings merged into result."""
        conn, today = conn_scored
        with patch(
            "vnalpha.data_availability.ensure_symbol_analysis_ready",
            return_value=_make_partial_result("FPT", today, ["data incomplete"]),
        ):
            parsed = parse(f"/compare FPT HPG --date {today}")
            result = reg.execute(
                parsed, conn=conn, registry=reg, tool_executor=_make_tool_executor(conn)
            )
        assert result.status == "PARTIAL"
        assert any("data incomplete" in w for w in result.warnings)

    def test_compare_mixed_ready_and_failed(self, conn_scored, reg):
        """7.7: one symbol READY, other FAILED → result still succeeds with warnings."""
        conn, today = conn_scored
        call_count = [0]

        def _mixed_ensure(conn, sym, dt, **kwargs):
            call_count[0] += 1
            if sym == "FPT":
                return _make_ready_result(sym, dt)
            return _make_failed_result(sym, dt)

        with patch(
            "vnalpha.data_availability.ensure_symbol_analysis_ready",
            side_effect=_mixed_ensure,
        ):
            parsed = parse(f"/compare FPT HPG --date {today}")
            result = reg.execute(
                parsed, conn=conn, registry=reg, tool_executor=_make_tool_executor(conn)
            )
        assert result.status == "PARTIAL"
        assert call_count[0] == 2


class TestNLPathEnsure:
    """Tasks 8.6-8.7: ensure triggered in assistant executor for NL path."""

    def test_executor_ensure_called_for_explain_step(self, conn_scored):
        """8.6: executor calls ensure before candidate.explain tool."""
        conn, today = conn_scored
        from vnalpha.assistant.executor import AssistantExecutor
        from vnalpha.assistant.models import AssistantPlan, ToolPlanStep

        ensure_calls: list[str] = []

        def _track_ensure(conn, sym, dt, **kwargs):
            ensure_calls.append(sym)
            return _make_ready_result(sym, dt)

        plan = AssistantPlan(
            intent="explain FPT",
            steps=[
                ToolPlanStep(
                    step_id="s1",
                    tool_name="candidate.explain",
                    arguments={"symbol": "FPT", "date": today},
                    purpose="explain FPT",
                    required_permission="ALLOW",
                )
            ],
        )
        executor = AssistantExecutor(conn, assistant_session_id="test-session")

        with patch(
            "vnalpha.data_availability.ensure_symbol_analysis_ready",
            _track_ensure,
        ):
            executor.execute(plan)

        assert "FPT" in ensure_calls

    def test_executor_ensure_called_for_compare_step(self, conn_scored):
        """8.7: executor calls ensure for each symbol in candidate.compare."""
        conn, today = conn_scored
        from vnalpha.assistant.executor import AssistantExecutor
        from vnalpha.assistant.models import AssistantPlan, ToolPlanStep

        ensure_calls: list[str] = []

        def _track_ensure(conn, sym, dt, **kwargs):
            ensure_calls.append(sym)
            return _make_ready_result(sym, dt)

        plan = AssistantPlan(
            intent="compare FPT HPG",
            steps=[
                ToolPlanStep(
                    step_id="s1",
                    tool_name="candidate.compare",
                    arguments={"symbols": ["FPT", "HPG"], "date": today},
                    purpose="compare FPT and HPG",
                    required_permission="ALLOW",
                )
            ],
        )
        executor = AssistantExecutor(conn, assistant_session_id="test-session")

        with patch(
            "vnalpha.data_availability.ensure_symbol_analysis_ready",
            _track_ensure,
        ):
            executor.execute(plan)

        assert "FPT" in ensure_calls
        assert "HPG" in ensure_calls
