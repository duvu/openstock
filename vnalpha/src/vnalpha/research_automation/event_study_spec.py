from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final

_SPEC_VERSION: Final = "event-study-spec-v1"
_MAX_HORIZON: Final = 60
_ALLOWED_FIELDS: Final = frozenset(
    {
        "close",
        "ma20",
        "ma50",
        "ma100",
        "ma20_slope",
        "ma50_slope",
        "volume_ratio",
        "atr14",
        "return_20d",
        "return_60d",
        "rs_20d_vs_vnindex",
        "rs_60d_vs_vnindex",
        "distance_to_ma20",
        "distance_to_52w_high",
        "base_range_30d",
        "close_strength",
        "volatility_20d",
    }
)
_ALLOWED_OPERATORS: Final = frozenset({">", ">=", "<", "<=", "==", "!="})
_CLAUSE_RE: Final = re.compile(
    r"^([a-zA-Z][a-zA-Z0-9_]*)\s*(>=|<=|==|!=|>|<)\s*(-?(?:\d+(?:\.\d*)?|\.\d+))$"
)


@dataclass(frozen=True, slots=True)
class EventCondition:
    field: str
    operator: str
    value: float

    def __post_init__(self) -> None:
        if self.field not in _ALLOWED_FIELDS:
            raise ValueError(f"Unsupported event-study field: {self.field}")
        if self.operator not in _ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported event-study operator: {self.operator}")

    def canonical(self) -> str:
        return f"{self.field} {self.operator} {format(self.value, '.12g')}"


@dataclass(frozen=True, slots=True)
class EventStudySpec:
    conditions: tuple[EventCondition, ...]
    horizon_sessions: int
    price_basis: str = "canonical_raw_unadjusted"
    metric_policy_version: str = "forward-close-return-v1"
    spec_version: str = _SPEC_VERSION

    def __post_init__(self) -> None:
        if not self.conditions:
            raise ValueError("At least one event-study condition is required.")
        if not 1 <= self.horizon_sessions <= _MAX_HORIZON:
            raise ValueError(
                f"Event-study horizon must be between 1 and {_MAX_HORIZON} sessions."
            )

    @property
    def canonical_condition(self) -> str:
        return " AND ".join(condition.canonical() for condition in self.conditions)

    def payload(self) -> dict[str, object]:
        return {
            "spec_version": self.spec_version,
            "conditions": [
                {
                    "field": condition.field,
                    "operator": condition.operator,
                    "value": condition.value,
                }
                for condition in self.conditions
            ],
            "horizon_sessions": self.horizon_sessions,
            "price_basis": self.price_basis,
            "metric_policy_version": self.metric_policy_version,
        }

    @property
    def specification_hash(self) -> str:
        encoded = json.dumps(
            self.payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def sql_predicate(self, alias: str = "f") -> tuple[str, list[float]]:
        clauses = [
            f'{alias}."{condition.field}" {condition.operator} ?'
            for condition in self.conditions
        ]
        return " AND ".join(clauses), [condition.value for condition in self.conditions]


def parse_event_study_spec(description: str, horizon_sessions: int) -> EventStudySpec:
    raw = description.strip()
    if not raw:
        raise ValueError("Event-study condition must not be empty.")
    clauses = re.split(r"\s+and\s+", raw, flags=re.IGNORECASE)
    conditions: list[EventCondition] = []
    for clause in clauses:
        match = _CLAUSE_RE.fullmatch(clause.strip())
        if match is None:
            raise ValueError(
                "Unsupported or ambiguous event-study condition. Use allowlisted "
                "numeric comparisons such as 'rs_20d_vs_vnindex > 0' joined by AND."
            )
        field, operator, value = match.groups()
        conditions.append(EventCondition(field.lower(), operator, float(value)))
    return EventStudySpec(tuple(conditions), horizon_sessions)


__all__ = [
    "EventCondition",
    "EventStudySpec",
    "parse_event_study_spec",
]
