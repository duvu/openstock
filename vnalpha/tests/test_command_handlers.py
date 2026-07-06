"""Integration tests for command handlers using fixture warehouse data (Task 5.9)."""

from __future__ import annotations

from datetime import date

import pytest

from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.warehouse.migrations import run_migrations


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
            },
        )

    # Insert watchlist
    for rank, sym, score_val, cls in [
        (1, "FPT", 0.82, "STRONG_CANDIDATE"),
        (2, "VNM", 0.55, "WATCH_CANDIDATE"),
    ]:
        conn.execute(
            """
            INSERT INTO daily_watchlist (date, rank, symbol, score, candidate_class, setup_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [today, rank, sym, score_val, cls, "ACCUMULATION_BASE"],
        )

    # Insert a session for /history tests
    sid = create_research_session(conn, surface="cli", command_text="/scan", command_name="scan")
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
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert len(result.tables) == 1
        assert len(result.tables[0].rows) == 2

    def test_scan_empty_watchlist(self, conn, reg):
        parsed = parse("/scan --date 2000-01-01")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert "empty" in result.summary.lower() or "No candidates" in result.summary

    def test_scan_with_universe_hint(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/scan VN30 --date {today}")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"


# ---------------------------------------------------------------------------
# /filter
# ---------------------------------------------------------------------------


class TestFilterHandler:
    def test_filter_by_score(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/filter score>=0.70 --date {today}")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        # Only FPT qualifies
        assert len(result.tables[0].rows) == 1
        assert result.tables[0].rows[0][0] == "FPT"

    def test_filter_by_class(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/filter class=STRONG_CANDIDATE --date {today}")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert any("FPT" in str(row) for row in result.tables[0].rows)


# ---------------------------------------------------------------------------
# /compare
# ---------------------------------------------------------------------------


class TestCompareHandler:
    def test_compare_returns_table(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/compare FPT VNM --date {today}")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert len(result.tables) == 1
        assert len(result.tables[0].rows) == 2

    def test_compare_no_symbols_validation_error(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse("/compare")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# /explain
# ---------------------------------------------------------------------------


class TestExplainHandler:
    def test_explain_returns_panels(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/explain FPT --date {today}")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        panel_titles = [p.title for p in result.panels]
        assert "Score Summary" in panel_titles
        assert "Score Breakdown" in panel_titles
        assert "Risk Flags" in panel_titles
        assert "Lineage" in panel_titles

    def test_explain_no_symbol_validation_error(self, conn, reg):
        parsed = parse("/explain")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "VALIDATION_ERROR"

    def test_explain_missing_score_graceful(self, conn, reg):
        parsed = parse("/explain FPT --date 2000-01-01")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert result.summary is not None


# ---------------------------------------------------------------------------
# /quality
# ---------------------------------------------------------------------------


class TestQualityHandler:
    def test_quality_watchlist_level(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/quality --date {today}")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"

    def test_quality_symbol_level_missing(self, conn, reg):
        parsed = parse("/quality FPT --date 2000-01-01")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert result.summary is not None


# ---------------------------------------------------------------------------
# /lineage
# ---------------------------------------------------------------------------


class TestLineageHandler:
    def test_lineage_returns_panel(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse(f"/lineage FPT --date {today}")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert len(result.panels) == 1
        assert "scoring_version" in str(result.panels[0].content)

    def test_lineage_no_symbol_validation_error(self, conn, reg):
        parsed = parse("/lineage")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# /note
# ---------------------------------------------------------------------------


class TestNoteHandler:
    def test_note_persists(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse('/note FPT "watch RS persistence"')
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert "FPT" in result.title

        # Verify persisted
        from vnalpha.warehouse.session_repo import list_research_notes
        notes = list_research_notes(conn, symbol="FPT")
        assert any("RS persistence" in n["note_text"] for n in notes)

    def test_note_missing_text_validation_error(self, conn, reg):
        parsed = parse("/note FPT")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# /history
# ---------------------------------------------------------------------------


class TestHistoryHandler:
    def test_history_returns_sessions(self, conn_with_data, reg):
        conn, today = conn_with_data
        parsed = parse("/history --limit 10")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert len(result.tables) == 1

    def test_history_empty(self, conn, reg):
        parsed = parse("/history")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert "No research sessions" in result.summary


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------


class TestHelpHandler:
    def test_help_lists_all_commands(self, conn, reg):
        parsed = parse("/help")
        result = reg.execute(parsed, conn=conn, registry=reg)
        assert result.status == "SUCCESS"
        assert len(result.tables) == 1
        # Should include all 9 commands
        all_names = [row[0] for row in result.tables[0].rows]
        for cmd in ["/scan", "/filter", "/compare", "/explain", "/quality", "/lineage", "/note", "/history", "/help"]:
            assert cmd in all_names, f"{cmd} not in help table"
