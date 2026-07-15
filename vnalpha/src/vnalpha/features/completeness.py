from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final


class FeatureCompletenessProfile(str, Enum):
    MINIMAL_20 = "MINIMAL_20"
    STANDARD_120 = "STANDARD_120"
    FULL_252 = "FULL_252"


class CompletenessStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    LEGACY_UNKNOWN = "LEGACY_UNKNOWN"


class FreshnessIssue(str, Enum):
    STALE_DATE = "STALE_DATE"


@dataclass(frozen=True, slots=True)
class FeatureCompletenessInput:
    observed_bar_count: int
    exact_date: bool
    values: Mapping[str, float | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class FeatureCompleteness:
    profile: FeatureCompletenessProfile
    neutral_status: CompletenessStatus
    relative_strength_status: CompletenessStatus
    required_bar_count: int
    observed_bar_count: int
    missing_neutral_fields: tuple[str, ...]
    missing_relative_strength_fields: tuple[str, ...]
    rule_version: str
    freshness_issue: FreshnessIssue | None


@dataclass(frozen=True, slots=True)
class ProfileRule:
    required_bar_count: int
    neutral_fields: tuple[str, ...]
    relative_strength_fields: tuple[str, ...]


RULE_VERSION: Final = "feature-completeness-v1"

_MINIMAL_NEUTRAL_FIELDS: Final = ("close", "ma20", "ma50", "return_20d")
_STANDARD_NEUTRAL_FIELDS: Final = (
    *_MINIMAL_NEUTRAL_FIELDS,
    "ma100",
    "ma20_slope",
    "ma50_slope",
    "volume_ma20",
    "volume_ratio",
    "atr14",
    "return_60d",
    "distance_to_ma20",
    "base_range_30d",
    "close_strength",
    "volatility_20d",
)
_FULL_NEUTRAL_FIELDS: Final = (*_STANDARD_NEUTRAL_FIELDS, "distance_to_52w_high")

_PROFILE_RULES: Final = MappingProxyType(
    {
        FeatureCompletenessProfile.MINIMAL_20: ProfileRule(
            required_bar_count=20,
            neutral_fields=_MINIMAL_NEUTRAL_FIELDS,
            relative_strength_fields=("rs_20d",),
        ),
        FeatureCompletenessProfile.STANDARD_120: ProfileRule(
            required_bar_count=120,
            neutral_fields=_STANDARD_NEUTRAL_FIELDS,
            relative_strength_fields=("rs_20d", "rs_60d"),
        ),
        FeatureCompletenessProfile.FULL_252: ProfileRule(
            required_bar_count=252,
            neutral_fields=_FULL_NEUTRAL_FIELDS,
            relative_strength_fields=("rs_20d", "rs_60d"),
        ),
    }
)


def evaluate_feature_completeness(
    feature_input: FeatureCompletenessInput,
) -> FeatureCompleteness:
    profile = _profile_for_history(feature_input.observed_bar_count)
    rule = _PROFILE_RULES[profile]
    missing_neutral_fields = _missing_fields(feature_input.values, rule.neutral_fields)
    freshness_issue = None if feature_input.exact_date else FreshnessIssue.STALE_DATE
    neutral_status = _neutral_status(
        feature_input.observed_bar_count,
        rule.required_bar_count,
        missing_neutral_fields,
        freshness_issue,
    )
    missing_relative_strength_fields = _missing_fields(
        feature_input.values, rule.relative_strength_fields
    )
    relative_strength_status = _relative_strength_status(
        missing_relative_strength_fields
    )
    return FeatureCompleteness(
        profile=profile,
        neutral_status=neutral_status,
        relative_strength_status=relative_strength_status,
        required_bar_count=rule.required_bar_count,
        observed_bar_count=feature_input.observed_bar_count,
        missing_neutral_fields=missing_neutral_fields,
        missing_relative_strength_fields=missing_relative_strength_fields,
        rule_version=RULE_VERSION,
        freshness_issue=freshness_issue,
    )


def _profile_for_history(observed_bar_count: int) -> FeatureCompletenessProfile:
    if observed_bar_count >= 252:
        return FeatureCompletenessProfile.FULL_252
    if observed_bar_count >= 120:
        return FeatureCompletenessProfile.STANDARD_120
    return FeatureCompletenessProfile.MINIMAL_20


def _missing_fields(
    values: Mapping[str, float | None], required_fields: tuple[str, ...]
) -> tuple[str, ...]:
    return tuple(field for field in required_fields if values.get(field) is None)


def _neutral_status(
    observed_bar_count: int,
    required_bar_count: int,
    missing_fields: tuple[str, ...],
    freshness_issue: FreshnessIssue | None,
) -> CompletenessStatus:
    if observed_bar_count < required_bar_count:
        return CompletenessStatus.INCOMPLETE
    if missing_fields:
        return CompletenessStatus.INCOMPLETE
    if freshness_issue is not None:
        return CompletenessStatus.INCOMPLETE
    return CompletenessStatus.COMPLETE


def _relative_strength_status(
    missing_fields: tuple[str, ...],
) -> CompletenessStatus:
    if missing_fields:
        return CompletenessStatus.INCOMPLETE
    return CompletenessStatus.COMPLETE
