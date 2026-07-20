"""Manual evidence gate for RankingPolicy promotion (issue #263).

Defines when a RankingPolicy may move from EXPERIMENTAL to a reviewed research
status using immutable, mature evidence. No automatic promotion or weight
change exists; a reviewed decision references exact evidence.
"""

from vnalpha.ranking_policy_gate.gate import (
    ACTIVATING_STATUSES,
    DEFAULT_PROMOTION_RULE,
    EvidenceSummary,
    PromotionRule,
    RankingDecisionStatus,
    assess_promotion,
    record_decision,
)

__all__ = [
    "ACTIVATING_STATUSES",
    "DEFAULT_PROMOTION_RULE",
    "EvidenceSummary",
    "PromotionRule",
    "RankingDecisionStatus",
    "assess_promotion",
    "record_decision",
]
