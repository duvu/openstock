"""Typed classification of missing canonical OHLCV sessions."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import assert_never


class LifecycleState(str, Enum):
    """Lifecycle states relevant to expected OHLCV publication."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class OHLCVGapKind(str, Enum):
    """Distinct missing-session states retained in maintenance evidence."""

    HOLIDAY_OR_NON_TRADING = "HOLIDAY_OR_NON_TRADING"
    NOT_YET_PUBLISHED = "NOT_YET_PUBLISHED"
    SUSPENDED_OR_INACTIVE = "SUSPENDED_OR_INACTIVE"
    PROVIDER_EMPTY = "PROVIDER_EMPTY"
    TRUE_GAP = "TRUE_GAP"


@dataclass(frozen=True, slots=True)
class GapDetectionInput:
    """Resolved inputs for classifying expected canonical sessions."""

    expected_sessions: tuple[date, ...]
    canonical_sessions: frozenset[date]
    lifecycle: LifecycleState
    resolved_market_date: date
    provider_empty: bool


@dataclass(frozen=True, slots=True)
class OHLCVGap:
    """One expected session absent from canonical OHLCV data."""

    session_date: date
    kind: OHLCVGapKind


@dataclass(frozen=True, slots=True)
class OHLCVGapReport:
    """Gap observations with true repair candidates exposed separately."""

    gaps: tuple[OHLCVGap, ...]

    @property
    def true_gap_dates(self) -> tuple[date, ...]:
        """Return only dates eligible for a bounded repair request."""
        return tuple(
            gap.session_date for gap in self.gaps if gap.kind is OHLCVGapKind.TRUE_GAP
        )


def detect_ohlcv_gaps(gap_input: GapDetectionInput) -> OHLCVGapReport:
    """Classify every missing expected session without collapsing its cause."""
    gaps = tuple(
        OHLCVGap(
            session_date=session_date,
            kind=_classify_missing_session(gap_input, session_date),
        )
        for session_date in gap_input.expected_sessions
        if session_date not in gap_input.canonical_sessions
    )
    return OHLCVGapReport(gaps=gaps)


def _classify_missing_session(
    gap_input: GapDetectionInput, session_date: date
) -> OHLCVGapKind:
    if session_date > gap_input.resolved_market_date:
        return OHLCVGapKind.NOT_YET_PUBLISHED

    match gap_input.lifecycle:
        case LifecycleState.ACTIVE:
            if gap_input.provider_empty:
                return OHLCVGapKind.PROVIDER_EMPTY
            return OHLCVGapKind.TRUE_GAP
        case LifecycleState.SUSPENDED | LifecycleState.INACTIVE:
            return OHLCVGapKind.SUSPENDED_OR_INACTIVE
        case unreachable:
            assert_never(unreachable)
