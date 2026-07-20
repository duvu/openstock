"""Tests for the verified manual RankingPolicy promotion gate."""

from __future__ import annotations

import json

import duckdb
import pytest

from vnalpha.ranking_policy_gate import (
    DEFAULT_PROMOTION_RULE,
    EvidenceSummary,
    RankingDecisionStatus,
    assess_promotion,
    record_decision,
)
from vnalpha.ranking_policy_gate.gate import (
    EvidenceVerificationError,
    get_decisions,
    verify_evidence,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _summary(**overrides) -> EvidenceSummary:
    values = {
        "policy_id": "baseline",
        "policy_version": "v2",
        "policy_hash": "hashabc",
        "evidence_cutoff_date": "2026-06-30",
        "sample_count": 999,
        "period_count": 999,
        "coverage": 1.0,
        "evaluation_manifest_ids": ("eval-1", "eval-2", "eval-3"),
        "replay_ids": ("replay-1",),
        "ranking_run_refs": (
            "2026-01-05:hashabc",
            "2026-02-05:hashabc",
            "2026-03-05:hashabc",
        ),
    }
    values.update(overrides)
    return EvidenceSummary(**values)


def _seed_manifest(
    conn,
    manifest_id,
    day,
    *,
    policy_hash="hashabc",
    complete=20,
    eligible=20,
    status="SUFFICIENT",
):
    conn.execute(
        """
        INSERT INTO ranking_evaluation_manifest_v2 (
            manifest_id, watchlist_date, horizon_sessions, top_n, price_basis,
            adjustment_version, scoring_policy_id, scoring_policy_version,
            scoring_policy_hash, ranking_run_ref, eligible_population,
            complete_population, incomplete_population, sufficiency_status,
            market_regime, assumptions_hash, eligible_population_hash,
            outcome_rows_hash, dataset_hash, contract_version
        ) VALUES (?, ?, 20, 10, 'RAW_UNADJUSTED', 'NONE', 'baseline', 'v2',
                  ?, ?, ?, ?, ?, ?, 'BULL', 'assumptions-1', ?, ?, ?,
                  'ranking-evaluation-v2')
        """,
        [
            manifest_id,
            day,
            policy_hash,
            f"{day}:{policy_hash}",
            eligible,
            complete,
            eligible - complete,
            status,
            f"population-{manifest_id}",
            f"outcomes-{manifest_id}",
            f"dataset-{manifest_id}",
        ],
    )


def _seed_verified_bundle(conn, *, complete=20, eligible=20, status="SUFFICIENT"):
    days = ("2026-01-05", "2026-02-05", "2026-03-05")
    manifests = ("eval-1", "eval-2", "eval-3")
    for manifest_id, day in zip(manifests, days, strict=True):
        _seed_manifest(
            conn,
            manifest_id,
            day,
            complete=complete,
            eligible=eligible,
            status=status,
        )
    refs = [f"{day}:hashabc" for day in days]
    conn.execute(
        """
        INSERT INTO ranking_replay_v2 (
            replay_id, spec_hash, dataset_hash, result_hash,
            scoring_policy_hash, ranking_run_refs_json,
            evaluation_manifest_ids_json, eligible_universe_hashes_json,
            membership_resolver_version, start_date, end_date,
            horizon_sessions, top_n, price_basis, adjustment_version,
            benchmark_symbol, rebalance_frequency, holding_policy,
            liquidity_policy_version, cost_bps, period_count,
            compounded_total_return, exclusions_json, caveats_json,
            event_ledger_json, spec_json, contract_version
        ) VALUES ('replay-1', 'spec-1', 'replay-dataset', 'result-1',
                  'hashabc', ?, ?, '["u1","u2","u3"]', 'pit-membership-v1',
                  '2026-01-05', '2026-03-05', 20, 10, 'RAW_UNADJUSTED',
                  'NONE', 'VNINDEX', 'EVERY_RANKING_DATE',
                  'FIXED_DECLARED_HORIZON', 'NO_LIQUIDITY_FILTER_V1', 0, 3,
                  0.10, '[]', '[]', '[]', '{}', 'ranking-replay-v2')
        """,
        [json.dumps(refs), json.dumps(list(manifests))],
    )


def test_pure_threshold_assessment_remains_deterministic() -> None:
    low_sample = assess_promotion(_summary(sample_count=5))
    one_period = assess_promotion(_summary(period_count=1))
    low_coverage = assess_promotion(_summary(coverage=0.1))
    assert not low_sample.eligible
    assert not one_period.eligible
    assert not low_coverage.eligible


def test_verification_recomputes_counts_and_ignores_caller_claims(conn) -> None:
    _seed_verified_bundle(conn, complete=20, eligible=25)
    verified = verify_evidence(
        conn,
        _summary(sample_count=1, period_count=1, coverage=0.01),
    )
    assert verified.sample_count == 60
    assert verified.period_count == 3
    assert verified.coverage == pytest.approx(0.8)
    assert verified.verification_status == "VERIFIED"
    assert verified.evidence_bundle_hash


def test_unknown_or_after_cutoff_evidence_fails_closed(conn) -> None:
    with pytest.raises(EvidenceVerificationError, match="Unknown"):
        verify_evidence(conn, _summary())
    _seed_verified_bundle(conn)
    with pytest.raises(EvidenceVerificationError, match="cutoff"):
        verify_evidence(
            conn,
            _summary(evidence_cutoff_date="2026-02-01"),
        )


def test_mixed_policy_evidence_fails_closed(conn) -> None:
    _seed_manifest(conn, "eval-1", "2026-01-05", policy_hash="other")
    _seed_manifest(conn, "eval-2", "2026-02-05")
    _seed_manifest(conn, "eval-3", "2026-03-05")
    with pytest.raises(EvidenceVerificationError, match="different policy"):
        verify_evidence(
            conn,
            _summary(replay_ids=()),
        )


def test_cannot_accept_partial_or_insufficient_verified_evidence(conn) -> None:
    _seed_verified_bundle(conn, complete=2, eligible=20, status="INSUFFICIENT")
    with pytest.raises(ValueError, match="insufficient evidence"):
        record_decision(
            conn,
            _summary(),
            status=RankingDecisionStatus.ACCEPTED,
            reviewer="analyst@example.com",
            rationale="looks good",
            reviewed_at="2026-07-01T00:00:00+07:00",
        )


def test_insufficient_and_research_validated_never_activate(conn) -> None:
    _seed_verified_bundle(conn, complete=2, eligible=20, status="INSUFFICIENT")
    insufficient = record_decision(
        conn,
        _summary(),
        status=RankingDecisionStatus.INSUFFICIENT_EVIDENCE,
        reviewer="analyst@example.com",
        rationale="not enough mature evidence",
        reviewed_at="2026-07-01T00:00:00+07:00",
    )
    row = conn.execute(
        "SELECT activates_policy FROM ranking_policy_decision WHERE decision_id = ?",
        [insufficient],
    ).fetchone()
    assert row == (False,)

    conn.execute("DELETE FROM ranking_policy_decision")
    conn.execute("DELETE FROM ranking_replay_v2")
    conn.execute("DELETE FROM ranking_evaluation_manifest_v2")
    _seed_verified_bundle(conn)
    validated = record_decision(
        conn,
        _summary(),
        status=RankingDecisionStatus.RESEARCH_VALIDATED,
        reviewer="analyst@example.com",
        rationale="informative but not activated",
        reviewed_at="2026-07-02T00:00:00+07:00",
    )
    assert conn.execute(
        "SELECT activates_policy FROM ranking_policy_decision WHERE decision_id = ?",
        [validated],
    ).fetchone() == (False,)


def test_accepted_decision_uses_exact_verified_bundle(conn) -> None:
    _seed_verified_bundle(conn)
    decision_id = record_decision(
        conn,
        _summary(),
        status=RankingDecisionStatus.ACCEPTED,
        reviewer="lead@example.com",
        rationale="reviewed exact manifests and replay",
        reviewed_at="2026-07-01T00:00:00+07:00",
        limitations=("historical research only",),
    )
    row = conn.execute(
        """
        SELECT activates_policy, evidence_bundle_hash,
               evidence_verification_status, sample_count, period_count
        FROM ranking_policy_decision WHERE decision_id = ?
        """,
        [decision_id],
    ).fetchone()
    assert row[0] is True
    assert row[1]
    assert row[2] == "VERIFIED"
    assert row[3:] == (60, 3)


def test_reviewer_required_and_history_is_append_only(conn) -> None:
    _seed_verified_bundle(conn)
    with pytest.raises(ValueError):
        record_decision(
            conn,
            _summary(),
            status=RankingDecisionStatus.RESEARCH_VALIDATED,
            reviewer="",
            rationale="x",
            reviewed_at="2026-07-01T00:00:00+07:00",
        )
    record_decision(
        conn,
        _summary(),
        status=RankingDecisionStatus.RESEARCH_VALIDATED,
        reviewer="a@example.com",
        rationale="first review",
        reviewed_at="2026-07-01T00:00:00+07:00",
    )
    record_decision(
        conn,
        _summary(),
        status=RankingDecisionStatus.ACCEPTED,
        reviewer="b@example.com",
        rationale="second reviewed decision",
        reviewed_at="2026-08-01T00:00:00+07:00",
    )
    decisions = get_decisions(conn, "baseline", "v2")
    assert [item["decision_status"] for item in decisions] == [
        "RESEARCH_VALIDATED",
        "ACCEPTED",
    ]


def test_rule_is_versioned_and_no_automatic_promotion_exists() -> None:
    assert DEFAULT_PROMOTION_RULE.rule_version == "ranking-promotion-rule-v2"
    assert DEFAULT_PROMOTION_RULE.min_sample_count > 1
    assert DEFAULT_PROMOTION_RULE.min_period_count > 1
