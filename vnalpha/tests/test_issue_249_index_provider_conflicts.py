"""Tests for issue #249: Resolve VNINDEX provider conflicts."""

from __future__ import annotations

from datetime import datetime

from vnalpha.ingestion.canonical_validation import (
    CanonicalCandidate,
    CanonicalValidationRule,
    validate_candidate,
)
from vnalpha.ingestion.index_provider_policy import (
    is_index_symbol,
    resolve_index_provider_conflict,
)


def test_vnindex_is_recognized_as_index() -> None:
    # Given: the VNINDEX symbol
    # When: checking if it's an index
    # Then: it is correctly identified
    assert is_index_symbol("VNINDEX")
    assert is_index_symbol("vnindex")
    assert is_index_symbol(" VNINDEX ")


def test_regular_equity_is_not_index() -> None:
    # Given: regular equity symbols
    # When: checking if they're indices
    # Then: they are not identified as indices
    assert not is_index_symbol("VCB")
    assert not is_index_symbol("FPT")
    assert not is_index_symbol("HPG")


def test_vci_has_priority_over_kbs_for_vnindex() -> None:
    # Given: conflicting VCI and KBS providers for VNINDEX
    # When: resolving the conflict
    resolution = resolve_index_provider_conflict("VNINDEX", ("vci", "kbs"))

    # Then: VCI is selected as authoritative
    assert resolution is not None
    assert resolution.selected_provider == "vci"
    assert "kbs" in resolution.rejected_providers


def test_kbs_is_used_when_vci_unavailable() -> None:
    # Given: only KBS and SSI available
    # When: resolving the conflict
    resolution = resolve_index_provider_conflict("VNINDEX", ("kbs", "ssi"))

    # Then: KBS is selected as next priority
    assert resolution is not None
    assert resolution.selected_provider == "kbs"
    assert "ssi" in resolution.rejected_providers


def test_no_resolution_for_non_index_symbols() -> None:
    # Given: a regular equity with multiple providers
    # When: attempting to resolve
    resolution = resolve_index_provider_conflict("VCB", ("vci", "kbs"))

    # Then: no resolution is available
    assert resolution is None


def test_no_resolution_when_no_preferred_provider_available() -> None:
    # Given: only unknown providers
    # When: attempting to resolve
    resolution = resolve_index_provider_conflict("VNINDEX", ("unknown1", "unknown2"))

    # Then: no resolution is available
    assert resolution is None


def test_vnindex_vci_passes_despite_kbs_conflict() -> None:
    # Given: the exact issue #249 scenario - VCI and KBS have different O/H/L
    vci_candidate = CanonicalCandidate(
        symbol="VNINDEX",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=1801.89,
        high=1803.14,
        low=1780.30,
        close=1787.45,
        volume=436669396.0,
        provider="vci",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    kbs_candidate = CanonicalCandidate(
        symbol="VNINDEX",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=1804.24,
        high=1804.24,
        low=1779.58,
        close=1787.45,
        volume=436669396.0,
        provider="kbs",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    # When: validating VCI candidate with KBS as peer
    rules = validate_candidate(vci_candidate, peer_candidates=(kbs_candidate,))

    # Then: VCI passes without provider consistency error
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY not in rules


def test_vnindex_kbs_fails_with_vci_conflict() -> None:
    # Given: KBS as candidate with VCI as competing provider
    kbs_candidate = CanonicalCandidate(
        symbol="VNINDEX",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=1804.24,
        high=1804.24,
        low=1779.58,
        close=1787.45,
        volume=436669396.0,
        provider="kbs",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    vci_candidate = CanonicalCandidate(
        symbol="VNINDEX",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=1801.89,
        high=1803.14,
        low=1780.30,
        close=1787.45,
        volume=436669396.0,
        provider="vci",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    # When: validating KBS candidate with VCI as peer
    rules = validate_candidate(kbs_candidate, peer_candidates=(vci_candidate,))

    # Then: KBS fails with provider consistency error (VCI takes precedence)
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY in rules


def test_regular_equity_still_requires_strict_consistency() -> None:
    # Given: two providers with different values for a regular stock
    vci_candidate = CanonicalCandidate(
        symbol="VCB",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000000.0,
        provider="vci",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    kbs_candidate = CanonicalCandidate(
        symbol="VCB",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=100.5,  # Different from VCI
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000000.0,
        provider="kbs",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    # When: validating either candidate
    vci_rules = validate_candidate(vci_candidate, peer_candidates=(kbs_candidate,))
    kbs_rules = validate_candidate(kbs_candidate, peer_candidates=(vci_candidate,))

    # Then: both fail with provider consistency error (no policy for equities)
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY in vci_rules
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY in kbs_rules


def test_vnindex_passes_when_providers_agree() -> None:
    # Given: VCI and KBS with identical OHLCV
    vci_candidate = CanonicalCandidate(
        symbol="VNINDEX",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=1787.45,
        high=1803.14,
        low=1780.30,
        close=1787.45,
        volume=436669396.0,
        provider="vci",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    kbs_candidate = CanonicalCandidate(
        symbol="VNINDEX",
        timestamp=datetime(2026, 7, 17, 9, 0),
        interval="1d",
        open=1787.45,
        high=1803.14,
        low=1780.30,
        close=1787.45,
        volume=436669396.0,
        provider="kbs",
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id="test-run",
    )

    # When: validating with agreement
    rules = validate_candidate(vci_candidate, peer_candidates=(kbs_candidate,))

    # Then: no provider consistency error
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY not in rules


def test_policy_version_is_tracked() -> None:
    # Given: a conflict resolution
    resolution = resolve_index_provider_conflict("VNINDEX", ("vci", "kbs"))

    # Then: policy version is recorded for auditability
    assert resolution is not None
    assert resolution.policy_version == "index_provider_v1"
    assert "precedence" in resolution.rationale.lower()
