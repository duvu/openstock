"""Integration tests: data-availability ensure wired into explain/compare handlers and NL path.

Tasks: 6.7-6.9 (explain handler), 7.6-7.7 (compare handler), 8.6-8.7 (NL path).
"""

from __future__ import annotations

from datetime import date

import duckdb
import pytest

from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.data_availability.models import (
    EnsureDataAction,
    EnsureDataResult,
    EnsureDataStatus,
)
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
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
                "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
                "scoring_policy_version": BASELINE_SCORING_POLICY.version,
                "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
                "scoring_policy_status": (
                    BASELINE_SCORING_POLICY.lifecycle_status.value
                ),
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
