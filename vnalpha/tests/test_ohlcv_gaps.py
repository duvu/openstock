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


def test_generic_calendar_queries_preserve_historical_range_compatibility() -> None:
    calendar = VietnamSessionCalendar()
    historical_monday = date(2025, 7, 14)

    assert calendar.is_session(historical_monday) is True
    assert calendar.sessions(
        SessionRange(start=historical_monday, end=date(2025, 7, 18))
    ) == tuple(date(2025, 7, day) for day in range(14, 19))
    assert calendar.rewind_sessions(historical_monday, 2) == date(2025, 7, 11)


def test_implicit_session_resolution_fails_closed_outside_versioned_coverage() -> None:
    calendar = VietnamSessionCalendar()

    with pytest.raises(CalendarCoverageError):
        calendar.latest_session_on_or_before(date(2027, 1, 4))


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
