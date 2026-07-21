"""Integration tests for command handlers using fixture warehouse data (Task 5.9)."""

from __future__ import annotations

from datetime import date

import pytest

from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.tools.executor import TracedLocalToolExecutor
from vnalpha.tools.setup import build_local_tool_registry
from vnalpha.warehouse.migrations import run_migrations


def _make_tool_executor(conn):
    """Build a TracedLocalToolExecutor wired to the given connection (session-scoped)."""
    registry = build_local_tool_registry(conn)
    return TracedLocalToolExecutor(conn, registry, session_id="test-session")


@pytest.fixture
def conn():
    """In-memory DuckDB with Phase 5 fixture data."""
    import duckdb

    c = duckdb.connect(":memory:")
    run_migrations(conn=c)
    yield c
    c.close()


@pytest.fixture
def conn_with_data(conn):
    """Connection pre-populated with candidate scores and watchlist data."""
    from vnalpha.warehouse.repositories import save_candidate_score
    from vnalpha.warehouse.session_repo import (
        create_research_session,
        finish_research_session,
    )

    today = date.today().isoformat()

    # Insert candidate scores
    for sym, score_val, cls in [
        ("FPT", 0.82, "STRONG_CANDIDATE"),
        ("VNM", 0.55, "WATCH_CANDIDATE"),
        ("HPG", 0.25, "IGNORE"),
    ]:
        save_candidate_score(
            conn,
            sym,
            today,
            {
                "score": score_val,
                "candidate_class": cls,
                "setup_type": "ACCUMULATION_BASE",
                "trend_score": 0.8,
                "relative_strength_score": 0.7,
                "volume_score": 0.6,
                "base_score": 0.5,
                "breakout_score": 0.4,
                "risk_quality_score": 0.9,
                "risk_flags": ["THIN_VOLUME"] if sym == "HPG" else [],
                "rule_outcomes": {},
                "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
                "scoring_policy_version": BASELINE_SCORING_POLICY.version,
                "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
                "scoring_policy_status": (
                    BASELINE_SCORING_POLICY.lifecycle_status.value
                ),
            },
        )

    # Insert watchlist
    for rank, sym, score_val, cls in [
        (1, "FPT", 0.82, "STRONG_CANDIDATE"),
        (2, "VNM", 0.55, "WATCH_CANDIDATE"),
    ]:
        conn.execute(
            """
            INSERT INTO daily_watchlist (
                date, rank, symbol, score, candidate_class, setup_type,
                scoring_policy_id, scoring_policy_version,
                scoring_policy_hash, scoring_policy_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                today,
                rank,
                sym,
                score_val,
                cls,
                "ACCUMULATION_BASE",
                BASELINE_SCORING_POLICY.policy_id,
                BASELINE_SCORING_POLICY.version,
                BASELINE_SCORING_POLICY.payload_hash,
                BASELINE_SCORING_POLICY.lifecycle_status.value,
            ],
        )

    # Insert a session for /history tests
    sid = create_research_session(
        conn, surface="cli", command_text="/scan", command_name="scan"
    )
    finish_research_session(conn, sid, status="SUCCESS")

    return conn, today


@pytest.fixture
def reg():
    return build_default_registry()


# ---------------------------------------------------------------------------
# /scan
# ---------------------------------------------------------------------------


class TestScanHandler:
    def test_scan_returns_watchlist(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/scan --date {today}")
        result = reg.execute(
            parsed, conn=conn, registry=reg, tool_executor=_make_tool_executor(conn)
        )
        assert result.status in {"SUCCESS", "PARTIAL"}
        assert len(result.tables) == 1
        assert len(result.tables[0].rows) == 2


# ---------------------------------------------------------------------------
# /filter
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /compare
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /explain
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /quality
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /lineage
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /note
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /history
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------
