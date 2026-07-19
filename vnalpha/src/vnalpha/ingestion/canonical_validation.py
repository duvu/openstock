"""Pure validation rules for candidate canonical OHLCV bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from vnalpha.ingestion.index_provider_policy import (
    is_index_symbol,
    resolve_index_provider_conflict,
)

CANONICAL_VALIDATION_VERSION = "canonical_ohlcv_v1"


class CanonicalValidationRule(str, Enum):
    """Severe rules that prevent an OHLCV bar becoming canonical."""

    CLOSE_POSITIVE = "close_positive"
    HIGH_BOUND = "high_bound"
    LOW_BOUND = "low_bound"
    VOLUME_NONNEGATIVE = "volume_nonnegative"
    INTERVAL_PRESENT = "interval_present"
    PRICE_BASIS_RAW_UNADJUSTED = "price_basis_raw_unadjusted"
    UPSTREAM_QUALITY_FAILED = "upstream_quality_failed"
    UPSTREAM_QUALITY_UNVERIFIED = "upstream_quality_unverified"
    PROVIDER_CONSISTENCY = "provider_consistency"


@dataclass(frozen=True, slots=True)
class CanonicalCandidate:
    """One raw observation considered for canonical selection."""

    symbol: str
    timestamp: datetime
    interval: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    provider: str | None
    price_basis: str | None
    quality_status: str | None
    ingestion_run_id: str


def validate_candidate(
    candidate: CanonicalCandidate,
    peer_candidates: tuple[CanonicalCandidate, ...] = (),
) -> tuple[CanonicalValidationRule, ...]:
    """Return severe validation rules triggered by one raw candidate.

    Passing observations for the same bar must agree across providers before
    the deterministically selected observation may enter canonical storage.

    For market indices, conflicting providers are resolved using versioned
    precedence policy rather than being rejected outright.
    """

    rules = list(_base_validation_rules(candidate))
    candidate_values = _ohlcv_values(candidate)

    # Find conflicting peer providers
    conflicting_peers = [
        peer
        for peer in peer_candidates
        if (
            _is_independently_valid_passing_observation(peer)
            and peer.provider != candidate.provider
            and _ohlcv_values(peer) != candidate_values
        )
    ]

    if conflicting_peers:
        # For indices, check if conflict can be resolved by provider policy
        if is_index_symbol(candidate.symbol):
            all_providers = tuple(
                {candidate.provider}
                | {p.provider for p in conflicting_peers if p.provider}
            )
            resolution = resolve_index_provider_conflict(
                candidate.symbol, all_providers
            )

            # Only apply consistency rule if candidate is not the selected provider
            if resolution and candidate.provider == resolution.selected_provider:
                # Candidate is the preferred provider - no consistency error
                pass
            elif resolution and candidate.provider in resolution.rejected_providers:
                # Candidate should be rejected in favor of preferred provider
                rules.append(CanonicalValidationRule.PROVIDER_CONSISTENCY)
            elif not resolution:
                # No policy available - fall back to consistency rule
                rules.append(CanonicalValidationRule.PROVIDER_CONSISTENCY)
        else:
            # Non-index: strict consistency required
            rules.append(CanonicalValidationRule.PROVIDER_CONSISTENCY)

    return tuple(rules)


def _base_validation_rules(
    candidate: CanonicalCandidate,
) -> tuple[CanonicalValidationRule, ...]:
    """Return the rules that do not depend on competing observations."""

    rules: list[CanonicalValidationRule] = []
    if candidate.close is None or candidate.close <= 0:
        rules.append(CanonicalValidationRule.CLOSE_POSITIVE)
    if candidate.high is not None:
        observed_highs = tuple(
            value
            for value in (candidate.open, candidate.close, candidate.low)
            if value is not None
        )
        if observed_highs and candidate.high < max(observed_highs):
            rules.append(CanonicalValidationRule.HIGH_BOUND)
    if candidate.low is not None:
        observed_lows = tuple(
            value
            for value in (candidate.open, candidate.close, candidate.high)
            if value is not None
        )
        if observed_lows and candidate.low > min(observed_lows):
            rules.append(CanonicalValidationRule.LOW_BOUND)
    if candidate.volume is not None and candidate.volume < 0:
        rules.append(CanonicalValidationRule.VOLUME_NONNEGATIVE)
    if not candidate.interval.strip():
        rules.append(CanonicalValidationRule.INTERVAL_PRESENT)
    if candidate.price_basis != "RAW_UNADJUSTED":
        rules.append(CanonicalValidationRule.PRICE_BASIS_RAW_UNADJUSTED)
    quality_status = (candidate.quality_status or "").strip().upper()
    if quality_status in {
        "ERROR",
        "FAIL",
        "FAILED",
        "INVALID",
    }:
        rules.append(CanonicalValidationRule.UPSTREAM_QUALITY_FAILED)
    elif quality_status not in {"PASS", "SUCCESS"}:
        rules.append(CanonicalValidationRule.UPSTREAM_QUALITY_UNVERIFIED)
    return tuple(rules)


def _is_independently_valid_passing_observation(
    candidate: CanonicalCandidate,
) -> bool:
    """Return whether a peer is eligible to challenge provider consistency."""

    return (
        candidate.quality_status is not None
        and candidate.quality_status.strip().lower() in {"pass", "success"}
        and not _base_validation_rules(candidate)
    )


def _ohlcv_values(candidate: CanonicalCandidate) -> tuple[float | None, ...]:
    """Return the values that must agree across independently valid providers."""

    return (
        candidate.open,
        candidate.high,
        candidate.low,
        candidate.close,
        candidate.volume,
    )
