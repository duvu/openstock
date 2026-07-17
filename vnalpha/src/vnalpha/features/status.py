from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Mapping, assert_never

FEATURE_STATUS_CONTRACT_VERSION: Final = "feature-data-status-v1"


class FeatureDataStatus(str, Enum):
    EXACT_DATE = "EXACT_DATE"
    STALE_DATE = "STALE_DATE"
    MISSING_BENCHMARK = "MISSING_BENCHMARK"


class FeatureEligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"


class FeatureExclusionReason(str, Enum):
    STALE_FEATURE_DATE = "STALE_FEATURE_DATE"
    MISSING_BENCHMARK = "MISSING_BENCHMARK"
    UNKNOWN_FEATURE_STATUS = "UNKNOWN_FEATURE_STATUS"


@dataclass(frozen=True, slots=True)
class FeatureEligibility:
    raw_status: str | None
    status: FeatureDataStatus | None
    eligibility_status: FeatureEligibilityStatus
    exclusion_reason: FeatureExclusionReason | None

    @property
    def eligible(self) -> bool:
        return self.eligibility_status is FeatureEligibilityStatus.ELIGIBLE


def parse_feature_eligibility(raw_status: str | None) -> FeatureEligibility:
    normalized = raw_status.strip().upper() if raw_status is not None else ""
    try:
        status = FeatureDataStatus(normalized)
    except ValueError:
        return FeatureEligibility(
            raw_status=raw_status,
            status=None,
            eligibility_status=FeatureEligibilityStatus.EXCLUDED,
            exclusion_reason=FeatureExclusionReason.UNKNOWN_FEATURE_STATUS,
        )

    match status:
        case FeatureDataStatus.EXACT_DATE:
            return FeatureEligibility(
                raw_status=raw_status,
                status=status,
                eligibility_status=FeatureEligibilityStatus.ELIGIBLE,
                exclusion_reason=None,
            )
        case FeatureDataStatus.STALE_DATE:
            reason = FeatureExclusionReason.STALE_FEATURE_DATE
        case FeatureDataStatus.MISSING_BENCHMARK:
            reason = FeatureExclusionReason.MISSING_BENCHMARK
        case unreachable:
            assert_never(unreachable)

    return FeatureEligibility(
        raw_status=raw_status,
        status=status,
        eligibility_status=FeatureEligibilityStatus.EXCLUDED,
        exclusion_reason=reason,
    )


def parse_feature_snapshot_eligibility(
    raw_status: str | None,
    raw_lineage: str | Mapping[str, Any] | None,
) -> FeatureEligibility:
    eligibility = parse_feature_eligibility(raw_status)
    if not eligibility.eligible:
        return eligibility
    lineage: Mapping[str, Any]
    if isinstance(raw_lineage, str):
        try:
            decoded = json.loads(raw_lineage)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        lineage = decoded if isinstance(decoded, Mapping) else {}
    elif isinstance(raw_lineage, Mapping):
        lineage = raw_lineage
    else:
        lineage = {}
    if lineage.get("feature_status_contract_version") == (
        FEATURE_STATUS_CONTRACT_VERSION
    ):
        return eligibility
    return FeatureEligibility(
        raw_status=raw_status,
        status=eligibility.status,
        eligibility_status=FeatureEligibilityStatus.EXCLUDED,
        exclusion_reason=FeatureExclusionReason.UNKNOWN_FEATURE_STATUS,
    )


__all__ = [
    "FEATURE_STATUS_CONTRACT_VERSION",
    "FeatureDataStatus",
    "FeatureEligibility",
    "FeatureEligibilityStatus",
    "FeatureExclusionReason",
    "parse_feature_eligibility",
    "parse_feature_snapshot_eligibility",
]
