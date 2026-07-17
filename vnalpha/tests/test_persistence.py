"""Tests for candidate_score persistence — save/read/upsert behavior.

Covers:
- save_candidate_score persists all fields correctly
- get_candidate_score returns the full record with parsed JSON
- get_candidate_scores returns all records for a date ordered by score
- Upsert behavior for (symbol, date) conflicts
- Evidence includes scoring_version, generated_at in lineage
- Taxonomy: candidate_class is in the canonical set
"""

from __future__ import annotations

import pytest

from vnalpha.core.types import CandidateClass, SetupType
from vnalpha.scoring.policy import BASELINE_SCORING_POLICY
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.repositories import (
    SCORING_VERSION,
    get_candidate_score,
    get_candidate_scores,
    save_candidate_score,
)

CANONICAL_CLASSES = {c.value for c in CandidateClass}
CANONICAL_SETUP_TYPES = {s.value for s in SetupType}


@pytest.fixture
def conn():
    c = in_memory_connection()
    run_migrations(conn=c)
    yield c
    c.close()


def _make_score_result(
    score: float = 0.75,
    candidate_class: str = "STRONG_CANDIDATE",
    setup_type: str = "ACCUMULATION_BASE",
    risk_flags: list | None = None,
) -> dict:
    return {
        "score": score,
        "candidate_class": candidate_class,
        "setup_type": setup_type,
        "trend_score": 0.80,
        "relative_strength_score": 0.70,
        "volume_score": 0.65,
        "base_score": 0.60,
        "breakout_score": 0.55,
        "risk_quality_score": 0.90,
        "risk_flags": risk_flags or [],
        "rule_outcomes": {"ma20_above_ma50": True, "volume_expansion": True},
        "scoring_policy_id": BASELINE_SCORING_POLICY.policy_id,
        "scoring_policy_version": BASELINE_SCORING_POLICY.version,
        "scoring_policy_hash": BASELINE_SCORING_POLICY.payload_hash,
        "scoring_policy_status": BASELINE_SCORING_POLICY.lifecycle_status.value,
    }


class TestSaveAndGetCandidateScore:
    def test_save_then_get_returns_record(self, conn):
        result = _make_score_result()
        save_candidate_score(conn, "FPT", "2024-06-28", result)
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        assert record is not None
        assert record["symbol"] == "FPT"
        assert record["date"] == "2024-06-28"
        assert abs(record["score"] - 0.75) < 0.001

    def test_get_returns_none_when_absent(self, conn):
        assert get_candidate_score(conn, "MISSING", "2024-06-28") is None

    def test_persists_all_score_components(self, conn):
        result = _make_score_result()
        save_candidate_score(conn, "FPT", "2024-06-28", result)
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        assert abs(record["trend_score"] - 0.80) < 0.001
        assert abs(record["relative_strength_score"] - 0.70) < 0.001
        assert abs(record["volume_score"] - 0.65) < 0.001
        assert abs(record["base_score"] - 0.60) < 0.001
        assert abs(record["breakout_score"] - 0.55) < 0.001
        assert abs(record["risk_quality_score"] - 0.90) < 0.001

    def test_candidate_class_persisted(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result())
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        assert record["candidate_class"] == "STRONG_CANDIDATE"

    def test_setup_type_persisted(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result())
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        assert record["setup_type"] == "ACCUMULATION_BASE"

    def test_risk_flags_persisted_as_list(self, conn):
        result = _make_score_result(risk_flags=["HIGH_ATR", "OVERBOUGHT"])
        save_candidate_score(conn, "FPT", "2024-06-28", result)
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        flags = record["risk_flags_json"]
        assert isinstance(flags, list)
        assert "HIGH_ATR" in flags
        assert "OVERBOUGHT" in flags

    def test_evidence_json_is_dict(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result())
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        assert isinstance(record["evidence_json"], dict)

    def test_lineage_json_is_dict(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result())
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        assert isinstance(record["lineage_json"], dict)

    def test_lineage_includes_scoring_version(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result())
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        lineage = record["lineage_json"]
        assert "scoring_version" in lineage
        assert lineage["scoring_version"] == SCORING_VERSION

    def test_lineage_includes_generated_at(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result())
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        lineage = record["lineage_json"]
        assert "generated_at" in lineage
        assert lineage["generated_at"] is not None

    def test_lineage_includes_feature_date(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result())
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        lineage = record["lineage_json"]
        assert lineage.get("feature_date") == "2024-06-28"


class TestUpsertBehavior:
    def test_upsert_updates_score(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.60))
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.80))
        record = get_candidate_score(conn, "FPT", "2024-06-28")
        assert abs(record["score"] - 0.80) < 0.001

    def test_upsert_is_deterministic_for_symbol_date(self, conn):
        """Only one row per (symbol, date) — no duplicates."""
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.60))
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.80))
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_score WHERE symbol = 'FPT' AND date = '2024-06-28'"
        ).fetchone()[0]
        assert count == 1

    def test_different_dates_are_separate_rows(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-27", _make_score_result(score=0.70))
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.75))
        count = conn.execute(
            "SELECT COUNT(*) FROM candidate_score WHERE symbol = 'FPT'"
        ).fetchone()[0]
        assert count == 2


class TestGetCandidateScores:
    def test_returns_all_for_date(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.80))
        save_candidate_score(conn, "VNM", "2024-06-28", _make_score_result(score=0.65))
        save_candidate_score(conn, "HPG", "2024-06-28", _make_score_result(score=0.55))
        results = get_candidate_scores(conn, "2024-06-28")
        assert len(results) == 3

    def test_ordered_by_score_descending(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.55))
        save_candidate_score(conn, "VNM", "2024-06-28", _make_score_result(score=0.80))
        save_candidate_score(conn, "HPG", "2024-06-28", _make_score_result(score=0.65))
        results = get_candidate_scores(conn, "2024-06-28")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.80))
        save_candidate_score(conn, "VNM", "2024-06-28", _make_score_result(score=0.30))
        results = get_candidate_scores(conn, "2024-06-28", min_score=0.50)
        assert len(results) == 1
        assert results[0]["symbol"] == "FPT"

    def test_empty_result_for_unknown_date(self, conn):
        results = get_candidate_scores(conn, "2099-01-01")
        assert results == []

    def test_different_dates_not_mixed(self, conn):
        save_candidate_score(conn, "FPT", "2024-06-27", _make_score_result(score=0.80))
        save_candidate_score(conn, "VNM", "2024-06-28", _make_score_result(score=0.70))
        results = get_candidate_scores(conn, "2024-06-28")
        assert len(results) == 1
        assert results[0]["symbol"] == "VNM"


class TestCandidateTaxonomyConformance:
    def test_canonical_classes_are_valid(self):
        for cls in ["STRONG_CANDIDATE", "WATCH_CANDIDATE", "WEAK_CANDIDATE", "IGNORE"]:
            assert cls in CANONICAL_CLASSES

    def test_save_all_canonical_classes(self, conn):
        for i, cls in enumerate(
            ["STRONG_CANDIDATE", "WATCH_CANDIDATE", "WEAK_CANDIDATE", "IGNORE"]
        ):
            result = _make_score_result(candidate_class=cls)
            save_candidate_score(conn, f"SYM{i}", "2024-06-28", result)
            record = get_candidate_score(conn, f"SYM{i}", "2024-06-28")
            assert record["candidate_class"] == cls


class TestWatchlistFromPersistedScores:
    """Verify watchlist generation reads from candidate_score, not recompute."""

    def test_watchlist_derives_from_candidate_score(self, conn):
        """Watchlist rows should come from candidate_score not fresh computation."""
        from vnalpha.scoring.generate_watchlist import save_watchlist

        # Insert candidate scores directly (bypassing score computation)
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.80))
        save_candidate_score(conn, "VNM", "2024-06-28", _make_score_result(score=0.65))
        # Save watchlist from persisted scores
        saved = save_watchlist(conn, "2024-06-28", top_n=10, min_score=0.40)
        assert saved == 2
        # Verify watchlist entries match candidate scores
        from vnalpha.warehouse.repositories import get_watchlist

        wl_rows = get_watchlist(conn, "2024-06-28")
        assert len(wl_rows) == 2
        assert wl_rows[0]["symbol"] == "FPT"  # higher score first
        assert abs(wl_rows[0]["score"] - 0.80) < 0.001

    def test_ignore_class_excluded_from_watchlist(self, conn):
        """IGNORE candidates should not appear in daily_watchlist."""
        from vnalpha.scoring.generate_watchlist import save_watchlist

        save_candidate_score(
            conn,
            "FPT",
            "2024-06-28",
            _make_score_result(score=0.80, candidate_class="IGNORE"),
        )
        save_candidate_score(conn, "VNM", "2024-06-28", _make_score_result(score=0.75))
        saved = save_watchlist(conn, "2024-06-28", top_n=10, min_score=0.40)
        assert saved == 1  # Only VNM (not FPT which is IGNORE)

    def test_empty_watchlist_when_no_candidates_qualify(self, conn):
        from vnalpha.scoring.generate_watchlist import save_watchlist

        # All below min_score
        save_candidate_score(conn, "FPT", "2024-06-28", _make_score_result(score=0.20))
        saved = save_watchlist(conn, "2024-06-28", top_n=10, min_score=0.40)
        assert saved == 0
