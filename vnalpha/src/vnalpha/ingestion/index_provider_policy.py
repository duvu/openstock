"""Versioned, auditable policy for conflicting index-provider observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

INDEX_PROVIDER_POLICY_VERSION = "index_provider_v2_family_scoped"


class IndexProviderPreference(str, Enum):
    VCI = "vci"
    KBS = "kbs"
    SSI = "ssi"


_POLICY_BY_FAMILY: dict[str, tuple[IndexProviderPreference, ...]] = {
    "HOSE": (
        IndexProviderPreference.VCI,
        IndexProviderPreference.KBS,
        IndexProviderPreference.SSI,
    ),
    "HNX": (
        IndexProviderPreference.KBS,
        IndexProviderPreference.VCI,
        IndexProviderPreference.SSI,
    ),
    "UPCOM": (
        IndexProviderPreference.KBS,
        IndexProviderPreference.VCI,
        IndexProviderPreference.SSI,
    ),
}

# Backward-compatible default for callers/tests that inspect the original name.
INDEX_PROVIDER_PRECEDENCE = _POLICY_BY_FAMILY["HOSE"]

_INDEX_FAMILY = {
    "VNINDEX": "HOSE",
    "VN30": "HOSE",
    "HNXINDEX": "HNX",
    "HNX30": "HNX",
    "UPCOM": "UPCOM",
    "UPCOMINDEX": "UPCOM",
}


@dataclass(frozen=True, slots=True)
class IndexConflictResolution:
    selected_provider: str
    rejected_providers: tuple[str, ...]
    policy_version: str
    policy_family: str
    rationale: str


def is_index_symbol(symbol: str) -> bool:
    return symbol.strip().upper() in _INDEX_FAMILY


def resolve_index_provider_conflict(
    symbol: str,
    provider_candidates: tuple[str, ...],
) -> IndexConflictResolution | None:
    normalized_symbol = symbol.strip().upper()
    family = _INDEX_FAMILY.get(normalized_symbol)
    if family is None:
        return None
    normalized_providers = tuple(
        provider.strip().lower() for provider in provider_candidates if provider
    )
    precedence = _POLICY_BY_FAMILY[family]
    for preferred in precedence:
        if preferred.value in normalized_providers:
            rejected = tuple(
                provider
                for provider in provider_candidates
                if provider and provider.strip().lower() != preferred.value
            )
            return IndexConflictResolution(
                selected_provider=preferred.value,
                rejected_providers=rejected,
                policy_version=INDEX_PROVIDER_POLICY_VERSION,
                policy_family=family,
                rationale=(
                    f"{family} index-provider precedence selected "
                    f"{preferred.value}; policy is deterministic and records all "
                    "passing conflicting source observations without claiming "
                    "generic cross-provider equality."
                ),
            )
    return None


__all__ = [
    "INDEX_PROVIDER_POLICY_VERSION",
    "INDEX_PROVIDER_PRECEDENCE",
    "IndexConflictResolution",
    "IndexProviderPreference",
    "is_index_symbol",
    "resolve_index_provider_conflict",
]
