from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

from vnalpha.scoring.policy import PolicyLifecycleStatus

DEFAULT_SCORING_POLICY_CONTEXT = "global"


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _to_status(value: Any) -> PolicyLifecycleStatus:
    if isinstance(value, PolicyLifecycleStatus):
        return value
    if isinstance(value, str):
        return PolicyLifecycleStatus(value)
    raise TypeError(f"Unsupported status value: {value!r}")


@dataclass(frozen=True, slots=True)
class ScoringPolicyDecision:
    """Immutable representation of one reviewed scoring policy decision."""

    decision_id: str
    policy_id: str
    policy_version: str
    policy_hash: str
    status: PolicyLifecycleStatus
    effective_date: date
    reviewer: str
    rationale: str
    evidence_json: str
    limitations_json: str
    reviewed_at: datetime
    decision_cutoff_date: date | None = None
    created_at: datetime | None = None

    @property
    def policy_key(self) -> str:
        return f"{self.policy_id}@{self.policy_version}"

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ScoringPolicyDecision":
        return cls(
            decision_id=str(row["decision_id"]),
            policy_id=str(row["scoring_policy_id"]),
            policy_version=str(row["scoring_policy_version"]),
            policy_hash=str(row["scoring_policy_hash"]),
            status=_to_status(row["decision_status"]),
            effective_date=_to_date(row["effective_date"]),
            reviewer=str(row["reviewer"]),
            rationale=str(row["rationale"]),
            evidence_json=str(row["evidence_json"] or "[]"),
            limitations_json=str(row["limitations_json"] or "[]"),
            reviewed_at=_to_datetime(row["reviewed_at"]),
            decision_cutoff_date=_to_date(row["decision_cutoff_date"])
            if row["decision_cutoff_date"]
            else None,
            created_at=_to_datetime(row["created_at"]) if row["created_at"] else None,
        )


__all__ = [
    "DEFAULT_SCORING_POLICY_CONTEXT",
    "ScoringPolicyDecision",
]
