"""Policy checks for persisted market and sector context snapshots."""

from __future__ import annotations

from datetime import date

from vnalpha.data_availability.deep_readiness_models import ContextIssue
from vnalpha.research_intelligence.breadth import MINIMUM_BREADTH_ROWS
from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
    SymbolSectorAlignment,
)
from vnalpha.research_intelligence.regime import (
    METHODOLOGY_VERSION as MARKET_METHODOLOGY_VERSION,
)
from vnalpha.research_intelligence.sector import (
    METHODOLOGY_VERSION as SECTOR_METHODOLOGY_VERSION,
)


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
    if (
        snapshot.breadth_eligible_count < MINIMUM_BREADTH_ROWS
        or snapshot.breadth_coverage is None
        or snapshot.breadth_coverage < 1.0
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
    snapshot = snapshots[0]
    if snapshot.as_of_date != target_date:
        return (ContextIssue.SECTOR_STRENGTH_STALE,)
    if snapshot.methodology_version != SECTOR_METHODOLOGY_VERSION:
        return (ContextIssue.SECTOR_INPUT_COVERAGE_INSUFFICIENT,)
    if snapshot.metadata_coverage < 1.0 or snapshot.unclassified_count:
        return (ContextIssue.SECTOR_METADATA_INSUFFICIENT,)
    if snapshot.quality != "OK":
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
    return ()


def freshness(issues: tuple[ContextIssue, ...]) -> str:
    """Render freshness without interpreting free-form warning text."""
    return (
        "stale"
        if ContextIssue.MARKET_REGIME_STALE in issues
        or ContextIssue.SECTOR_STRENGTH_STALE in issues
        else "unavailable"
    )
