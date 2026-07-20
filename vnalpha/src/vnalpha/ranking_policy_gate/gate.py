"""RankingPolicy promotion gate logic + persistence (issue #263)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import duckdb

RANKING_POLICY_DECISION_CONTRACT_VERSION = "ranking-policy-decision-v1"


class RankingDecisionStatus(str, Enum):
    """Reviewed decision vocabulary (issue #263)."""

    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RESEARCH_VALIDATED = "RESEARCH_VALIDATED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


# Statuses that may activate a policy. INSUFFICIENT_EVIDENCE and
# RESEARCH_VALIDATED never activate a policy on their own.
ACTIVATING_STATUSES: frozenset[RankingDecisionStatus] = frozenset(
    {RankingDecisionStatus.ACCEPTED}
)


@dataclass(frozen=True, slots=True)
class PromotionRule:
    """Versioned minimum evidence thresholds for promotion eligibility."""

    rule_version: str
    min_sample_count: int
    min_period_count: int
    min_coverage: float


DEFAULT_PROMOTION_RULE = PromotionRule(
    rule_version="ranking-promotion-rule-v1",
    min_sample_count=30,
    min_period_count=3,
    min_coverage=0.5,
)


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    """Mature evidence gathered for one policy promotion assessment.

    All counts must derive from evidence at or before ``evidence_cutoff_date``;
    the caller is responsible for excluding later evidence.
    """

    policy_id: str
    policy_version: str
    policy_hash: str
    evidence_cutoff_date: str
    sample_count: int
    period_count: int
    coverage: float
    evaluation_manifest_ids: tuple[str, ...] = ()
    replay_ids: tuple[str, ...] = ()
    ranking_run_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromotionAssessment:
    eligible: bool
    reasons: tuple[str, ...]
    rule_version: str


def assess_promotion(
    evidence: EvidenceSummary, rule: PromotionRule = DEFAULT_PROMOTION_RULE
) -> PromotionAssessment:
    """Decide whether evidence is sufficient to support a promotion decision.

    Fails closed: tiny samples, too few periods, or thin coverage make the
    evidence INSUFFICIENT. This never promotes anything — it only reports
    whether a reviewer *may* record an activating decision.
    """
    reasons: list[str] = []
    if evidence.sample_count < rule.min_sample_count:
        reasons.append(
            f"sample_count {evidence.sample_count} < {rule.min_sample_count}"
        )
    if evidence.period_count < rule.min_period_count:
        reasons.append(
            f"period_count {evidence.period_count} < {rule.min_period_count}"
        )
    if evidence.coverage < rule.min_coverage:
        reasons.append(f"coverage {evidence.coverage:.2f} < {rule.min_coverage:.2f}")
    if not evidence.evaluation_manifest_ids:
        reasons.append("no baseline evaluation evidence referenced")
    return PromotionAssessment(
        eligible=not reasons,
        reasons=tuple(reasons),
        rule_version=rule.rule_version,
    )


def record_decision(
    conn: duckdb.DuckDBPyConnection,
    evidence: EvidenceSummary,
    *,
    status: RankingDecisionStatus,
    reviewer: str,
    rationale: str,
    reviewed_at: str,
    limitations: tuple[str, ...] = (),
    rule: PromotionRule = DEFAULT_PROMOTION_RULE,
) -> str:
    """Persist one immutable, append-only reviewed decision.

    Enforces the gate contract:
    - An activating status (ACCEPTED) is rejected when the evidence is
      INSUFFICIENT under ``rule`` — a policy cannot be promoted on thin/partial
      evidence, and there is no automatic promotion path.
    - INSUFFICIENT_EVIDENCE and RESEARCH_VALIDATED never activate a policy.
    - A human reviewer and rationale are required; history is never mutated.
    """
    if not reviewer or not rationale:
        raise ValueError("reviewer and rationale are required")

    assessment = assess_promotion(evidence, rule)
    activates = status in ACTIVATING_STATUSES

    if activates and not assessment.eligible:
        raise ValueError(
            "cannot record an activating decision on insufficient evidence: "
            + "; ".join(assessment.reasons)
        )
    if status is RankingDecisionStatus.INSUFFICIENT_EVIDENCE and assessment.eligible:
        # Guard against mislabelling: do not stamp INSUFFICIENT_EVIDENCE when the
        # thresholds are actually met.
        raise ValueError(
            "evidence meets thresholds; INSUFFICIENT_EVIDENCE is not applicable"
        )

    decision_id = f"rpd_{uuid4().hex[:16]}"
    conn.execute(
        """
        INSERT INTO ranking_policy_decision (
            decision_id, policy_id, policy_version, policy_hash, decision_status,
            rule_version, evidence_cutoff_date, sample_count, period_count,
            coverage, reviewer, rationale, limitations_json,
            evaluation_manifest_ids_json, replay_ids_json, ranking_run_refs_json,
            activates_policy, contract_version, reviewed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            decision_id,
            evidence.policy_id,
            evidence.policy_version,
            evidence.policy_hash,
            status.value,
            rule.rule_version,
            evidence.evidence_cutoff_date,
            evidence.sample_count,
            evidence.period_count,
            evidence.coverage,
            reviewer,
            rationale,
            json.dumps(list(limitations)),
            json.dumps(list(evidence.evaluation_manifest_ids)),
            json.dumps(list(evidence.replay_ids)),
            json.dumps(list(evidence.ranking_run_refs)),
            activates,
            RANKING_POLICY_DECISION_CONTRACT_VERSION,
            reviewed_at,
        ],
    )
    conn.commit()
    return decision_id


def get_decisions(
    conn: duckdb.DuckDBPyConnection, policy_id: str, policy_version: str
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT decision_id, decision_status, rule_version, evidence_cutoff_date,
               sample_count, period_count, coverage, reviewer, activates_policy,
               reviewed_at
        FROM ranking_policy_decision
        WHERE policy_id = ? AND policy_version = ?
        ORDER BY reviewed_at
        """,
        [policy_id, policy_version],
    ).fetchall()
    return [
        {
            "decision_id": r[0],
            "decision_status": r[1],
            "rule_version": r[2],
            "evidence_cutoff_date": str(r[3]),
            "sample_count": r[4],
            "period_count": r[5],
            "coverage": r[6],
            "reviewer": r[7],
            "activates_policy": bool(r[8]),
            "reviewed_at": str(r[9]),
        }
        for r in rows
    ]


__all__ = [
    "ACTIVATING_STATUSES",
    "DEFAULT_PROMOTION_RULE",
    "EvidenceSummary",
    "PromotionAssessment",
    "PromotionRule",
    "RankingDecisionStatus",
    "assess_promotion",
    "get_decisions",
    "record_decision",
]
