from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Mapping, assert_never

FEATURE_STATUS_CONTRACT_VERSION: Final = "feature-data-status-v1"
_FEATURE_STATUS_CONTRACT_KEY: Final = "feature_status_contract_version"


class _JsonObjectPairs(list[tuple[str, Any]]):
    pass


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
    contract_version: object | None = None
    if isinstance(raw_lineage, str):
        try:
            decoded = json.loads(raw_lineage, object_pairs_hook=_JsonObjectPairs)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if isinstance(decoded, _JsonObjectPairs):
            contract_values = [
                value for key, value in decoded if key == _FEATURE_STATUS_CONTRACT_KEY
            ]
            if len(contract_values) == 1:
                contract_version = contract_values[0]
    elif isinstance(raw_lineage, Mapping):
        contract_version = raw_lineage.get(_FEATURE_STATUS_CONTRACT_KEY)
    if contract_version == FEATURE_STATUS_CONTRACT_VERSION:
        return eligibility
    return FeatureEligibility(
        raw_status=raw_status,
        status=eligibility.status,
        eligibility_status=FeatureEligibilityStatus.EXCLUDED,
        exclusion_reason=FeatureExclusionReason.UNKNOWN_FEATURE_STATUS,
    )


def feature_exclusion_reason_sql(table_alias: str) -> str:
    if (
        not table_alias
        or not table_alias[0].isascii()
        or not table_alias[0].isalpha()
        or not all(
            character.isascii() and (character.isalnum() or character == "_")
            for character in table_alias
        )
    ):
        raise ValueError("table_alias must be an ASCII SQL identifier")
    status = f"upper(trim(coalesce({table_alias}.feature_data_status, '')))"
    contract_version = (
        "json_extract_string("
        f"try_cast({table_alias}.lineage_json AS JSON), "
        f"'$.{_FEATURE_STATUS_CONTRACT_KEY}')"
    )
    contract_key_count = (
        "list_count(list_filter("
        f"json_keys(try_cast({table_alias}.lineage_json AS JSON)), "
        f"contract_key -> contract_key = '{_FEATURE_STATUS_CONTRACT_KEY}'))"
    )
    return (
        "CASE "
        f"WHEN {status} = '{FeatureDataStatus.EXACT_DATE.value}' "
        f"AND {contract_key_count} = 1 "
        f"AND {contract_version} = '{FEATURE_STATUS_CONTRACT_VERSION}' THEN NULL "
        f"WHEN {status} = '{FeatureDataStatus.STALE_DATE.value}' "
        f"THEN '{FeatureExclusionReason.STALE_FEATURE_DATE.value}' "
        f"WHEN {status} = '{FeatureDataStatus.MISSING_BENCHMARK.value}' "
        f"THEN '{FeatureExclusionReason.MISSING_BENCHMARK.value}' "
        f"ELSE '{FeatureExclusionReason.UNKNOWN_FEATURE_STATUS.value}' END"
    )


def feature_eligibility_sql(table_alias: str) -> str:
    return f"({feature_exclusion_reason_sql(table_alias)}) IS NULL"


__all__ = [
    "FEATURE_STATUS_CONTRACT_VERSION",
    "FeatureDataStatus",
    "FeatureEligibility",
    "FeatureEligibilityStatus",
    "FeatureExclusionReason",
    "feature_eligibility_sql",
    "feature_exclusion_reason_sql",
    "parse_feature_eligibility",
    "parse_feature_snapshot_eligibility",
]
