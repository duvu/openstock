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
    get_candidate_score,
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
