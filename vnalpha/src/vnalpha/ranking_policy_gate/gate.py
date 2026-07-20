"""Manual RankingPolicy promotion gate over verified persisted evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import duckdb

RANKING_POLICY_DECISION_CONTRACT_VERSION = "ranking-policy-decision-v2"


class RankingDecisionStatus(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RESEARCH_VALIDATED = "RESEARCH_VALIDATED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


ACTIVATING_STATUSES: frozenset[RankingDecisionStatus] = frozenset(
    {RankingDecisionStatus.ACCEPTED}
)


@dataclass(frozen=True, slots=True)
class PromotionRule:
    rule_version: str
    min_sample_count: int
    min_period_count: int
    min_coverage: float


DEFAULT_PROMOTION_RULE = PromotionRule(
    rule_version="ranking-promotion-rule-v2",
    min_sample_count=30,
    min_period_count=3,
    min_coverage=0.5,
)


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    """Evidence references plus computed metrics.

    Callers may construct this object for pure threshold assessment, but
    ``record_decision`` always recomputes counts, coverage, policy identity and
    cutoffs from the referenced database artifacts before persistence.
    """

    policy_id: str
    policy_version: str
    policy_hash: str
    evidence_cutoff_date: str
    sample_count: int = 0
    period_count: int = 0
    coverage: float = 0.0
    evaluation_manifest_ids: tuple[str, ...] = ()
    replay_ids: tuple[str, ...] = ()
    ranking_run_refs: tuple[str, ...] = ()
    assumptions_hashes: tuple[str, ...] = ()
    dataset_hashes: tuple[str, ...] = ()
    evidence_bundle_hash: str | None = None
    verification_status: str = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class PromotionAssessment:
    eligible: bool
    reasons: tuple[str, ...]
    rule_version: str


class EvidenceVerificationError(ValueError):
    pass


def assess_promotion(
    evidence: EvidenceSummary,
    rule: PromotionRule = DEFAULT_PROMOTION_RULE,
) -> PromotionAssessment:
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
    if evidence.verification_status not in {"VERIFIED", "UNVERIFIED"}:
        reasons.append(f"evidence verification status is {evidence.verification_status}")
    return PromotionAssessment(
        eligible=not reasons,
        reasons=tuple(reasons),
        rule_version=rule.rule_version,
    )


def verify_evidence(
    conn: duckdb.DuckDBPyConnection,
    evidence: EvidenceSummary,
) -> EvidenceSummary:
    """Resolve and verify all manifest/replay references at the declared cutoff."""
    cutoff = evidence.evidence_cutoff_date
    manifests: list[dict[str, object]] = []
    for manifest_id in evidence.evaluation_manifest_ids:
        row = conn.execute(
            """
            SELECT manifest_id, watchlist_date, scoring_policy_id,
                   scoring_policy_version, scoring_policy_hash,
                   eligible_population, complete_population,
                   incomplete_population, sufficiency_status, assumptions_hash,
                   dataset_hash, ranking_run_ref, price_basis,
                   adjustment_version
            FROM ranking_evaluation_manifest_v2
            WHERE manifest_id = ?
            """,
            [manifest_id],
        ).fetchone()
        if row is None:
            raise EvidenceVerificationError(
                f"Unknown ranking evaluation manifest {manifest_id!r}"
            )
        if str(row[1]) > cutoff:
            raise EvidenceVerificationError(
                f"Manifest {manifest_id!r} lies after evidence cutoff {cutoff}"
            )
        if row[4] != evidence.policy_hash:
            raise EvidenceVerificationError(
                f"Manifest {manifest_id!r} belongs to a different policy"
            )
        if row[2] != evidence.policy_id or row[3] != evidence.policy_version:
            raise EvidenceVerificationError(
                f"Manifest {manifest_id!r} policy identity does not match request"
            )
        manifests.append(
            {
                "manifest_id": row[0],
                "date": str(row[1]),
                "eligible": int(row[5]),
                "complete": int(row[6]),
                "incomplete": int(row[7]),
                "sufficiency": row[8],
                "assumptions_hash": row[9],
                "dataset_hash": row[10],
                "ranking_run_ref": row[11],
                "price_basis": row[12],
                "adjustment_version": row[13],
            }
        )

    replays: list[dict[str, object]] = []
    for replay_id in evidence.replay_ids:
        row = conn.execute(
            """
            SELECT replay_id, end_date, scoring_policy_hash, period_count,
                   ranking_run_refs_json, evaluation_manifest_ids_json,
                   dataset_hash, price_basis, adjustment_version,
                   membership_resolver_version, caveats_json
            FROM ranking_replay_v2 WHERE replay_id = ?
            """,
            [replay_id],
        ).fetchone()
        if row is None:
            raise EvidenceVerificationError(f"Unknown replay {replay_id!r}")
        if str(row[1]) > cutoff:
            raise EvidenceVerificationError(
                f"Replay {replay_id!r} lies after evidence cutoff {cutoff}"
            )
        if row[2] != evidence.policy_hash:
            raise EvidenceVerificationError(
                f"Replay {replay_id!r} belongs to a different policy"
            )
        replay_manifest_ids = tuple(json.loads(row[5]))
        if not set(replay_manifest_ids).issubset(evidence.evaluation_manifest_ids):
            raise EvidenceVerificationError(
                f"Replay {replay_id!r} references unreviewed evaluation manifests"
            )
        caveats = tuple(json.loads(row[10]))
        if "future_data_contamination" in caveats:
            raise EvidenceVerificationError(
                f"Replay {replay_id!r} is marked future-contaminated"
            )
        replays.append(
            {
                "replay_id": row[0],
                "end_date": str(row[1]),
                "period_count": int(row[3]),
                "ranking_run_refs": tuple(json.loads(row[4])),
                "manifest_ids": replay_manifest_ids,
                "dataset_hash": row[6],
                "price_basis": row[7],
                "adjustment_version": row[8],
                "membership_resolver_version": row[9],
                "caveats": caveats,
            }
        )

    bases = {str(item["price_basis"]) for item in [*manifests, *replays]}
    adjustment_versions = {
        str(item["adjustment_version"]) for item in [*manifests, *replays]
    }
    if len(bases) > 1:
        raise EvidenceVerificationError(f"Mixed price bases: {sorted(bases)!r}")
    if len(adjustment_versions) > 1:
        raise EvidenceVerificationError(
            f"Mixed adjustment versions: {sorted(adjustment_versions)!r}"
        )

    assumptions_hashes = tuple(
        sorted({str(item["assumptions_hash"]) for item in manifests})
    )
    if len(assumptions_hashes) > 1:
        raise EvidenceVerificationError(
            "Evaluation manifests use different assumptions and are not comparable"
        )
    dataset_hashes = tuple(
        sorted(
            {
                str(item["dataset_hash"])
                for item in [*manifests, *replays]
                if item.get("dataset_hash")
            }
        )
    )
    ranking_refs = tuple(
        sorted(
            {
                str(item["ranking_run_ref"])
                for item in manifests
                if item.get("ranking_run_ref")
            }
            | {
                str(reference)
                for item in replays
                for reference in item["ranking_run_refs"]
            }
        )
    )
    if evidence.ranking_run_refs and set(evidence.ranking_run_refs) != set(ranking_refs):
        raise EvidenceVerificationError(
            "Caller ranking-run references do not match persisted evidence"
        )

    sample_count = sum(int(item["complete"]) for item in manifests)
    eligible_count = sum(int(item["eligible"]) for item in manifests)
    incomplete_count = sum(int(item["incomplete"]) for item in manifests)
    coverage = sample_count / eligible_count if eligible_count else 0.0
    period_dates = {str(item["date"]) for item in manifests}
    period_count = len(period_dates)
    if replays:
        period_count = max(period_count, max(int(item["period_count"]) for item in replays))
    verification_status = (
        "VERIFIED"
        if manifests
        and incomplete_count == 0
        and all(item["sufficiency"] == "SUFFICIENT" for item in manifests)
        else "PARTIAL"
    )
    bundle_payload = {
        "policy_hash": evidence.policy_hash,
        "cutoff": cutoff,
        "manifests": manifests,
        "replays": replays,
        "ranking_run_refs": ranking_refs,
        "assumptions_hashes": assumptions_hashes,
        "dataset_hashes": dataset_hashes,
    }
    bundle_hash = hashlib.sha256(
        json.dumps(
            bundle_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return replace(
        evidence,
        sample_count=sample_count,
        period_count=period_count,
        coverage=coverage,
        ranking_run_refs=ranking_refs,
        assumptions_hashes=assumptions_hashes,
        dataset_hashes=dataset_hashes,
        evidence_bundle_hash=bundle_hash,
        verification_status=verification_status,
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
    """Verify referenced evidence, then append one immutable human decision."""
    if not reviewer.strip() or not rationale.strip():
        raise ValueError("reviewer and rationale are required")
    verified = verify_evidence(conn, evidence)
    assessment = assess_promotion(verified, rule)
    activates = status in ACTIVATING_STATUSES
    if activates and (
        not assessment.eligible or verified.verification_status != "VERIFIED"
    ):
        reasons = [*assessment.reasons]
        if verified.verification_status != "VERIFIED":
            reasons.append(
                f"verification_status={verified.verification_status}"
            )
        raise ValueError(
            "cannot record an activating decision on insufficient evidence: "
            + "; ".join(reasons)
        )
    if status is RankingDecisionStatus.INSUFFICIENT_EVIDENCE and (
        assessment.eligible and verified.verification_status == "VERIFIED"
    ):
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
            activates_policy, contract_version, reviewed_at,
            evidence_bundle_hash, evidence_verification_status,
            assumptions_hashes_json, dataset_hashes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            decision_id,
            verified.policy_id,
            verified.policy_version,
            verified.policy_hash,
            status.value,
            rule.rule_version,
            verified.evidence_cutoff_date,
            verified.sample_count,
            verified.period_count,
            verified.coverage,
            reviewer,
            rationale,
            json.dumps(list(limitations)),
            json.dumps(list(verified.evaluation_manifest_ids)),
            json.dumps(list(verified.replay_ids)),
            json.dumps(list(verified.ranking_run_refs)),
            activates,
            RANKING_POLICY_DECISION_CONTRACT_VERSION,
            reviewed_at,
            verified.evidence_bundle_hash,
            verified.verification_status,
            json.dumps(list(verified.assumptions_hashes)),
            json.dumps(list(verified.dataset_hashes)),
        ],
    )
    conn.commit()
    return decision_id


def get_decisions(
    conn: duckdb.DuckDBPyConnection,
    policy_id: str,
    policy_version: str,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT decision_id, decision_status, rule_version, evidence_cutoff_date,
               sample_count, period_count, coverage, reviewer, activates_policy,
               reviewed_at, evidence_bundle_hash, evidence_verification_status
        FROM ranking_policy_decision
        WHERE policy_id = ? AND policy_version = ?
        ORDER BY reviewed_at
        """,
        [policy_id, policy_version],
    ).fetchall()
    return [
        {
            "decision_id": row[0],
            "decision_status": row[1],
            "rule_version": row[2],
            "evidence_cutoff_date": str(row[3]),
            "sample_count": row[4],
            "period_count": row[5],
            "coverage": row[6],
            "reviewer": row[7],
            "activates_policy": bool(row[8]),
            "reviewed_at": str(row[9]),
            "evidence_bundle_hash": row[10],
            "evidence_verification_status": row[11],
        }
        for row in rows
    ]


__all__ = [
    "ACTIVATING_STATUSES",
    "DEFAULT_PROMOTION_RULE",
    "EvidenceSummary",
    "EvidenceVerificationError",
    "PromotionAssessment",
    "PromotionRule",
    "RankingDecisionStatus",
    "assess_promotion",
    "get_decisions",
    "record_decision",
    "verify_evidence",
]
