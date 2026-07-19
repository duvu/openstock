from datetime import date

import pytest

from vnalpha.ingestion.ohlcv_gaps import (
    GapDetectionInput,
    LifecycleState,
    OHLCVGapKind,
    detect_ohlcv_gaps,
)
from vnalpha.ingestion.trading_calendar import (
    CalendarCoverageError,
    SessionRange,
    VietnamSessionCalendar,
)


def test_sessions_exclude_weekends_and_configured_holidays() -> None:
    # Given
    calendar = VietnamSessionCalendar(holidays=frozenset({date(2026, 9, 2)}))
    session_range = SessionRange(start=date(2026, 8, 31), end=date(2026, 9, 4))

    # When
    sessions = calendar.sessions(session_range)

    # Then
    assert sessions == (
        date(2026, 8, 31),
        date(2026, 9, 1),
        date(2026, 9, 3),
        date(2026, 9, 4),
    )


def test_calendar_queries_fail_closed_outside_versioned_coverage() -> None:
    calendar = VietnamSessionCalendar()
    unsupported = date(2027, 1, 4)

    with pytest.raises(CalendarCoverageError):
        calendar.is_session(unsupported)
    with pytest.raises(CalendarCoverageError):
        calendar.sessions(SessionRange(start=unsupported, end=unsupported))
    with pytest.raises(CalendarCoverageError):
        calendar.latest_session_on_or_before(unsupported)
    with pytest.raises(CalendarCoverageError):
        calendar.rewind_sessions(unsupported, 2)


def test_gap_detector_reports_active_published_missing_session_as_true_gap() -> None:
    # Given
    gap_input = GapDetectionInput(
        expected_sessions=(date(2026, 9, 1), date(2026, 9, 2)),
        canonical_sessions=frozenset({date(2026, 9, 1)}),
        lifecycle=LifecycleState.ACTIVE,
        resolved_market_date=date(2026, 9, 2),
        provider_empty=False,
    )

    # When
    report = detect_ohlcv_gaps(gap_input)

    # Then
    assert report.gaps[0].session_date == date(2026, 9, 2)
    assert report.gaps[0].kind is OHLCVGapKind.TRUE_GAP
    assert report.true_gap_dates == (date(2026, 9, 2),)


def test_gap_detector_distinguishes_future_and_suspended_missing_sessions() -> None:
    # Given
    future_input = GapDetectionInput(
        expected_sessions=(date(2026, 9, 3),),
        canonical_sessions=frozenset(),
        lifecycle=LifecycleState.ACTIVE,
        resolved_market_date=date(2026, 9, 2),
        provider_empty=False,
    )
    suspended_input = GapDetectionInput(
        expected_sessions=(date(2026, 9, 2),),
        canonical_sessions=frozenset(),
        lifecycle=LifecycleState.SUSPENDED,
        resolved_market_date=date(2026, 9, 2),
        provider_empty=False,
    )

    # When
    future_report = detect_ohlcv_gaps(future_input)
    suspended_report = detect_ohlcv_gaps(suspended_input)

    # Then
    assert future_report.gaps[0].kind is OHLCVGapKind.NOT_YET_PUBLISHED
    assert suspended_report.gaps[0].kind is OHLCVGapKind.SUSPENDED_OR_INACTIVE


def test_gap_detector_preserves_provider_empty_as_its_own_state() -> None:
    # Given
    gap_input = GapDetectionInput(
        expected_sessions=(date(2026, 9, 2),),
        canonical_sessions=frozenset(),
        lifecycle=LifecycleState.ACTIVE,
        resolved_market_date=date(2026, 9, 2),
        provider_empty=True,
    )

    # When
    report = detect_ohlcv_gaps(gap_input)

    # Then
    assert report.gaps[0].kind is OHLCVGapKind.PROVIDER_EMPTY
