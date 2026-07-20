"""Tests for issue #263: manual RankingPolicy promotion evidence gate."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.ranking_policy_gate import (
    DEFAULT_PROMOTION_RULE,
    EvidenceSummary,
    RankingDecisionStatus,
    assess_promotion,
    record_decision,
)
from vnalpha.ranking_policy_gate.gate import get_decisions
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _sufficient_evidence(**overrides) -> EvidenceSummary:
    base = {
        "policy_id": "baseline",
        "policy_version": "v2",
        "policy_hash": "hashabc",
        "evidence_cutoff_date": "2026-06-30",
        "sample_count": 50,
        "period_count": 5,
        "coverage": 0.8,
        "evaluation_manifest_ids": ("rankeval_1",),
        "replay_ids": ("replay_1",),
        "ranking_run_refs": ("2026-01-05:baseline",),
    }
    base.update(overrides)
    return EvidenceSummary(**base)


def test_tiny_sample_cannot_pass() -> None:
    assessment = assess_promotion(_sufficient_evidence(sample_count=5))
    assert assessment.eligible is False
    assert any("sample_count" in r for r in assessment.reasons)


def test_single_period_cannot_pass() -> None:
    assessment = assess_promotion(_sufficient_evidence(period_count=1))
    assert assessment.eligible is False
    assert any("period_count" in r for r in assessment.reasons)


def test_thin_coverage_cannot_pass() -> None:
    assessment = assess_promotion(_sufficient_evidence(coverage=0.1))
    assert assessment.eligible is False
    assert any("coverage" in r for r in assessment.reasons)


def test_missing_baseline_evidence_cannot_pass() -> None:
    assessment = assess_promotion(_sufficient_evidence(evaluation_manifest_ids=()))
    assert assessment.eligible is False


def test_sufficient_evidence_is_eligible() -> None:
    assessment = assess_promotion(_sufficient_evidence())
    assert assessment.eligible is True
    assert assessment.reasons == ()


def test_cannot_accept_on_insufficient_evidence(conn) -> None:
    with pytest.raises(ValueError, match="insufficient evidence"):
        record_decision(
            conn,
            _sufficient_evidence(sample_count=3),
            status=RankingDecisionStatus.ACCEPTED,
            reviewer="analyst@example.com",
            rationale="looks good",
            reviewed_at="2026-07-01T00:00:00+07:00",
        )


def test_insufficient_evidence_decision_does_not_activate(conn) -> None:
    decision_id = record_decision(
        conn,
        _sufficient_evidence(sample_count=3),
        status=RankingDecisionStatus.INSUFFICIENT_EVIDENCE,
        reviewer="analyst@example.com",
        rationale="not enough mature outcomes yet",
        reviewed_at="2026-07-01T00:00:00+07:00",
    )
    row = conn.execute(
        "SELECT activates_policy, decision_status FROM ranking_policy_decision "
        "WHERE decision_id = ?",
        [decision_id],
    ).fetchone()
    assert row[0] is False
    assert row[1] == "INSUFFICIENT_EVIDENCE"


def test_research_validated_does_not_activate(conn) -> None:
    decision_id = record_decision(
        conn,
        _sufficient_evidence(),
        status=RankingDecisionStatus.RESEARCH_VALIDATED,
        reviewer="analyst@example.com",
        rationale="informative vs baselines but not deployed",
        reviewed_at="2026-07-01T00:00:00+07:00",
    )
    row = conn.execute(
        "SELECT activates_policy FROM ranking_policy_decision WHERE decision_id = ?",
        [decision_id],
    ).fetchone()
    assert row[0] is False


def test_accepted_decision_activates_and_references_evidence(conn) -> None:
    decision_id = record_decision(
        conn,
        _sufficient_evidence(),
        status=RankingDecisionStatus.ACCEPTED,
        reviewer="lead@example.com",
        rationale="beats baselines across regimes with sufficient sample",
        reviewed_at="2026-07-01T00:00:00+07:00",
        limitations=("single market regime",),
    )
    row = conn.execute(
        "SELECT activates_policy, evaluation_manifest_ids_json, replay_ids_json "
        "FROM ranking_policy_decision WHERE decision_id = ?",
        [decision_id],
    ).fetchone()
    assert row[0] is True
    assert "rankeval_1" in row[1]
    assert "replay_1" in row[2]


def test_reviewer_and_rationale_required(conn) -> None:
    with pytest.raises(ValueError):
        record_decision(
            conn,
            _sufficient_evidence(),
            status=RankingDecisionStatus.RESEARCH_VALIDATED,
            reviewer="",
            rationale="x",
            reviewed_at="2026-07-01T00:00:00+07:00",
        )


def test_history_is_append_only_and_immutable(conn) -> None:
    record_decision(
        conn,
        _sufficient_evidence(),
        status=RankingDecisionStatus.RESEARCH_VALIDATED,
        reviewer="a@example.com",
        rationale="first review",
        reviewed_at="2026-07-01T00:00:00+07:00",
    )
    record_decision(
        conn,
        _sufficient_evidence(),
        status=RankingDecisionStatus.ACCEPTED,
        reviewer="b@example.com",
        rationale="promoted after more evidence",
        reviewed_at="2026-08-01T00:00:00+07:00",
    )
    decisions = get_decisions(conn, "baseline", "v2")
    # Both decisions retained in order; no overwrite.
    assert len(decisions) == 2
    assert decisions[0]["decision_status"] == "RESEARCH_VALIDATED"
    assert decisions[1]["decision_status"] == "ACCEPTED"


def test_no_automatic_promotion_default_rule_versioned() -> None:
    # The rule set is explicitly versioned so thresholds are auditable.
    assert DEFAULT_PROMOTION_RULE.rule_version == "ranking-promotion-rule-v1"
    assert DEFAULT_PROMOTION_RULE.min_sample_count > 1
    assert DEFAULT_PROMOTION_RULE.min_period_count > 1
