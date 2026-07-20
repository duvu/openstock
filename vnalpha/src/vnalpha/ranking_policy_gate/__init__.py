"""Manual evidence gate for RankingPolicy promotion."""

from vnalpha.ranking_policy_gate.gate import (
    ACTIVATING_STATUSES,
    DEFAULT_PROMOTION_RULE,
    EvidenceSummary,
    EvidenceVerificationError,
    PromotionAssessment,
    PromotionRule,
    RankingDecisionStatus,
    assess_promotion,
    get_decisions,
    record_decision,
    verify_evidence,
)

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
