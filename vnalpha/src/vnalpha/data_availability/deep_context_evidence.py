"""Policy checks for persisted market and sector context snapshots."""

from __future__ import annotations

from datetime import date

from vnalpha.data_availability.deep_readiness_models import ContextIssue
from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
    SymbolSectorAlignment,
)
from vnalpha.research_intelligence.policy import (
    PRODUCTION_MARKET_REGIME_POLICY,
    PRODUCTION_SECTOR_STRENGTH_POLICY,
)
from vnalpha.research_intelligence.regime import (
    METHODOLOGY_VERSION as MARKET_METHODOLOGY_VERSION,
)
from vnalpha.research_intelligence.sector import (
    METHODOLOGY_VERSION as SECTOR_METHODOLOGY_VERSION,
)


def _lineage_float(lineage: object, key: str) -> float | None:
    if not hasattr(lineage, "get"):
        return None
    try:
        value = lineage.get(key)  # type: ignore[attr-defined]
    except TypeError:
        return None
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def market_issues(
    snapshot: MarketRegimeSnapshot | None,
    latest: MarketRegimeSnapshot | None,
    target_date: date,
    build_failed: bool,
) -> tuple[ContextIssue, ...]:
    """Return public policy issues for one exact-date market snapshot."""
    if build_failed:
        return (ContextIssue.CONTEXT_BUILD_FAILED,)
    if snapshot is None:
        return (
            ContextIssue.MARKET_REGIME_STALE
            if latest is not None and latest.as_of_date != target_date
            else ContextIssue.MARKET_REGIME_MISSING,
        )
    if snapshot.as_of_date != target_date:
        return (ContextIssue.MARKET_REGIME_STALE,)
    if snapshot.methodology_version != MARKET_METHODOLOGY_VERSION:
        return (ContextIssue.MARKET_REGIME_QUALITY_UNACCEPTABLE,)

    policy = PRODUCTION_MARKET_REGIME_POLICY
    exchange_coverage = _lineage_float(snapshot.lineage, "exchange_coverage")
    liquidity_coverage = _lineage_float(snapshot.lineage, "liquidity_coverage")
    if (
        snapshot.breadth_eligible_count < policy.minimum_eligible_symbols
        or snapshot.breadth_coverage is None
        or snapshot.breadth_coverage < policy.minimum_breadth_coverage
        or exchange_coverage is None
        or exchange_coverage < policy.minimum_exchange_coverage
        or liquidity_coverage is None
        or liquidity_coverage < policy.minimum_liquidity_coverage
    ):
        return (ContextIssue.MARKET_REGIME_INPUT_COVERAGE_INSUFFICIENT,)
    if snapshot.quality != "COMPLETE" or snapshot.regime == "INSUFFICIENT_DATA":
        return (ContextIssue.MARKET_REGIME_QUALITY_UNACCEPTABLE,)
    return ()


def sector_issues(
    snapshots: list[SectorStrengthSnapshot],
    latest: list[SectorStrengthSnapshot],
    target_date: date,
    build_failed: bool,
) -> tuple[ContextIssue, ...]:
    """Return public policy issues for an exact-date sector snapshot set."""
    if build_failed:
        return (ContextIssue.CONTEXT_BUILD_FAILED,)
    if not snapshots:
        return (
            ContextIssue.SECTOR_STRENGTH_STALE
            if latest and latest[0].as_of_date != target_date
            else ContextIssue.SECTOR_STRENGTH_MISSING,
        )
    first = snapshots[0]
    if first.as_of_date != target_date:
        return (ContextIssue.SECTOR_STRENGTH_STALE,)
    if first.methodology_version != SECTOR_METHODOLOGY_VERSION:
        return (ContextIssue.SECTOR_INPUT_COVERAGE_INSUFFICIENT,)

    policy = PRODUCTION_SECTOR_STRENGTH_POLICY
    # Readiness for classification metadata is derived DIRECTLY from the
    # versioned policy coverage thresholds. Bounded missing classification is
    # permitted: a non-zero unclassified_count no longer fails readiness on its
    # own, because metadata_coverage already encodes it
    # (metadata_coverage == 1 - unclassified_count / active_count). Residual
    # unclassified symbols above the threshold are disclosed as caveats, not
    # treated as a hard failure. See market-context-methodology.md.
    #
    # Below-threshold sector classification (missing sector) and below-threshold
    # taxonomy name/version coverage have different remediation paths, so they
    # are reported as distinct typed issues. Missing classification is checked
    # first because taxonomy coverage is only meaningful over classified symbols.
    if first.metadata_coverage < policy.minimum_metadata_coverage:
        return (ContextIssue.SECTOR_METADATA_INSUFFICIENT,)
    if (
        _lineage_float(first.lineage, "taxonomy_coverage") or 0.0
    ) < policy.minimum_taxonomy_coverage:
        return (ContextIssue.SECTOR_TAXONOMY_INSUFFICIENT,)
    if (
        first.quality != "OK"
        or (_lineage_float(first.lineage, "liquidity_coverage") or 0.0)
        < policy.minimum_liquidity_coverage
    ):
        return (ContextIssue.SECTOR_INPUT_COVERAGE_INSUFFICIENT,)

    for snapshot in snapshots:
        sector_coverage = _lineage_float(snapshot.lineage, "sector_coverage")
        sector_liquidity_coverage = _lineage_float(
            snapshot.lineage, "sector_liquidity_coverage"
        )
        if (
            snapshot.methodology_version != SECTOR_METHODOLOGY_VERSION
            or snapshot.member_count < policy.minimum_sector_members
            or snapshot.eligible_count < policy.minimum_eligible_members
            or sector_coverage is None
            or sector_coverage < policy.minimum_sector_coverage
            or sector_liquidity_coverage is None
            or sector_liquidity_coverage < policy.minimum_liquidity_coverage
            or snapshot.quality != "OK"
        ):
            return (ContextIssue.SECTOR_INPUT_COVERAGE_INSUFFICIENT,)
    return ()


def alignment_issues(
    alignment: SymbolSectorAlignment | None, build_failed: bool
) -> tuple[ContextIssue, ...]:
    """Return the typed reason a symbol cannot use sector context."""
    if build_failed:
        return (ContextIssue.CONTEXT_BUILD_FAILED,)
    if alignment is None or alignment.sector is None:
        return (ContextIssue.SYMBOL_SECTOR_UNCLASSIFIED,)
    if alignment.snapshot is None:
        return (ContextIssue.SECTOR_NOT_RANKABLE,)
    if alignment.snapshot.methodology_version != SECTOR_METHODOLOGY_VERSION:
        return (ContextIssue.SECTOR_NOT_RANKABLE,)
    return ()


def freshness(issues: tuple[ContextIssue, ...]) -> str:
    """Render freshness without interpreting free-form warning text."""
    return (
        "stale"
        if ContextIssue.MARKET_REGIME_STALE in issues
        or ContextIssue.SECTOR_STRENGTH_STALE in issues
        else "unavailable"
    )
