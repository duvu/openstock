from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class PolicyLifecycleStatus(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    policy_id: str
    version: str
    lifecycle_status: PolicyLifecycleStatus
    effective_from: date
    effective_to: date | None
    payload: Mapping[str, Any]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        frozen_payload = _freeze(dict(self.payload))
        canonical = json.dumps(
            _plain(frozen_payload),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        object.__setattr__(self, "payload", frozen_payload)
        object.__setattr__(
            self,
            "payload_hash",
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    @classmethod
    def from_payload(
        cls,
        *,
        policy_id: str,
        version: str,
        lifecycle_status: PolicyLifecycleStatus,
        effective_from: date,
        payload: Mapping[str, Any],
        effective_to: date | None = None,
    ) -> ScoringPolicy:
        return cls(
            policy_id=policy_id,
            version=version,
            lifecycle_status=lifecycle_status,
            effective_from=effective_from,
            effective_to=effective_to,
            payload=payload,
        )

    def number(self, section: str, key: str) -> float:
        values = self.payload.get(section)
        if not isinstance(values, Mapping) or key not in values:
            raise ValueError(f"Scoring policy is missing {section}.{key}")
        return float(values[key])

    def require_effective(self, as_of_date: date) -> None:
        if as_of_date < self.effective_from or (
            self.effective_to is not None and as_of_date > self.effective_to
        ):
            raise ValueError(
                f"Scoring policy {self.policy_id}@{self.version} is not effective "
                f"on {as_of_date.isoformat()}"
            )


BASELINE_SCORING_POLICY = ScoringPolicy.from_payload(
    policy_id="openstock-candidate-score",
    version="v1.0",
    lifecycle_status=PolicyLifecycleStatus.EXPERIMENTAL,
    effective_from=date(2024, 1, 1),
    payload={
        "weights": {
            "trend": 0.30,
            "relative_strength": 0.25,
            "volume": 0.15,
            "base": 0.10,
            "breakout": 0.10,
            "risk_quality": 0.10,
        },
        "trend_rule_weights": {
            "price_above_ma20": 0.20,
            "price_above_ma50": 0.20,
            "ma20_above_ma50": 0.20,
            "ma50_above_ma100": 0.20,
            "positive_ma20_slope": 0.20,
        },
        "relative_strength_weights": {"rs20": 0.50, "rs60": 0.50},
        "breakout_rule_weights": {
            "near_52w_high": 0.25,
            "close_strength": 0.25,
            "volume_expansion": 0.25,
            "base_compression": 0.25,
        },
        "normalization": {
            "relative_strength_floor": -0.05,
            "relative_strength_range": 0.10,
            "volume_divisor": 2.0,
            "base_range": 0.15,
        },
        "risk": {"flag_penalty": 0.20},
        "candidate_thresholds": {"strong": 0.70, "watch": 0.50, "weak": 0.30},
        "setup_thresholds": {
            "base_compression": 0.08,
            "near_52w_high": -0.05,
            "breakout_volume": 1.50,
            "pullback_distance": 0.03,
        },
        "breakout_thresholds": {
            "near_52w_high": -0.05,
            "close_strength": 0.70,
            "volume_expansion": 1.20,
            "base_compression": 0.08,
        },
    },
)

_POLICIES = {
    (
        BASELINE_SCORING_POLICY.policy_id,
        BASELINE_SCORING_POLICY.version,
    ): BASELINE_SCORING_POLICY
}


def resolve_scoring_policy(
    policy_id: str = BASELINE_SCORING_POLICY.policy_id,
    version: str = BASELINE_SCORING_POLICY.version,
    *,
    as_of_date: date | str | None = None,
) -> ScoringPolicy:
    try:
        policy = _POLICIES[(policy_id, version)]
    except KeyError as exc:
        raise ValueError(f"Unknown scoring policy {policy_id}@{version}") from exc
    if as_of_date is not None:
        resolved_date = (
            as_of_date
            if isinstance(as_of_date, date)
            else date.fromisoformat(as_of_date)
        )
        policy.require_effective(resolved_date)
    return policy


__all__ = [
    "BASELINE_SCORING_POLICY",
    "PolicyLifecycleStatus",
    "ScoringPolicy",
    "resolve_scoring_policy",
]
