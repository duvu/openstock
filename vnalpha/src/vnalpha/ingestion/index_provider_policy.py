"""Versioned policy for resolving conflicting index provider observations.

When multiple independently-passing providers report different OHLCV values for
the same index bar, this module defines the auditable selection policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

INDEX_PROVIDER_POLICY_VERSION = "index_provider_v1"


class IndexProviderPreference(str, Enum):
    """Provider preference for Vietnamese market indices."""

    VCI = "vci"  # Priority 1: VCI (HOSE official data provider)
    KBS = "kbs"  # Priority 2: KBS Securities
    SSI = "ssi"  # Priority 3: SSI Securities


# Versioned provider precedence for Vietnamese indices
# Rationale: VCI is the official data provider for HOSE (Ho Chi Minh Stock Exchange)
# and is used as the authoritative source for VNINDEX
INDEX_PROVIDER_PRECEDENCE = (
    IndexProviderPreference.VCI,
    IndexProviderPreference.KBS,
    IndexProviderPreference.SSI,
)


@dataclass(frozen=True, slots=True)
class IndexConflictResolution:
    """Result of resolving conflicting index observations."""

    selected_provider: str
    rejected_providers: tuple[str, ...]
    policy_version: str = INDEX_PROVIDER_POLICY_VERSION
    rationale: str = "Provider precedence for Vietnamese market indices"


def is_index_symbol(symbol: str) -> bool:
    """Return whether a symbol represents a market index."""
    normalized = symbol.strip().upper()
    return normalized in {
        "VNINDEX",  # Ho Chi Minh Stock Exchange Index
        "VN30",     # VN30 Index
        "HNXINDEX", # Hanoi Stock Exchange Index
        "HNX30",    # HNX30 Index
        "UPCOM",    # UPCOM Index
    }


def resolve_index_provider_conflict(
    symbol: str,
    provider_candidates: tuple[str, ...],
) -> IndexConflictResolution | None:
    """Resolve conflicting providers for an index using versioned precedence.

    Returns:
        IndexConflictResolution if a provider can be selected, None if no
        resolution is available (e.g., non-index symbol or no preferred provider).
    """
    if not is_index_symbol(symbol):
        return None

    normalized_providers = tuple(p.strip().lower() for p in provider_candidates)

    # Select the highest-precedence provider that appears in candidates
    for preferred in INDEX_PROVIDER_PRECEDENCE:
        if preferred.value in normalized_providers:
            rejected = tuple(
                p for p in provider_candidates
                if p.strip().lower() != preferred.value
            )
            return IndexConflictResolution(
                selected_provider=preferred.value,
                rejected_providers=rejected,
            )

    return None
