"""Tests for issue #254: Calendar validity and expiry warnings."""

from __future__ import annotations

from datetime import date

import pytest

from vnalpha.ingestion.trading_calendar import (
    CalendarCoverageError,
    VietnamSessionCalendar,
)


def test_calendar_has_validity_metadata() -> None:
    # Given: the default calendar
    calendar = VietnamSessionCalendar()

    # Then: validity metadata is present
    assert calendar.valid_from == date(2026, 1, 1)
    assert calendar.valid_through == date(2026, 12, 31)
    assert calendar.version == "hnx-vnx-2026-1403-1517"
    assert len(calendar.sources) == 2


def test_calendar_is_not_near_expiry_early_in_year() -> None:
    # Given: a date early in the validity period
    calendar = VietnamSessionCalendar()
    current_date = date(2026, 3, 15)

    # When: checking expiry status
    is_near = calendar.is_near_expiry(current_date, warning_days=90)

    # Then: not near expiry
    assert not is_near


def test_calendar_is_near_expiry_within_90_days() -> None:
    # Given: a date 60 days before expiry
    calendar = VietnamSessionCalendar()
    current_date = date(2026, 11, 2)  # 59 days before Dec 31

    # When: checking with 90-day warning
    is_near = calendar.is_near_expiry(current_date, warning_days=90)

    # Then: within warning window
    assert is_near


def test_calendar_expiry_on_last_valid_day() -> None:
    # Given: the last valid day
    calendar = VietnamSessionCalendar()
    current_date = date(2026, 12, 31)

    # When: checking expiry
    is_near = calendar.is_near_expiry(current_date)

    # Then: within warning (0 days remaining)
    assert is_near


def test_coverage_status_returns_complete_metadata() -> None:
    # Given: a date mid-year
    calendar = VietnamSessionCalendar()
    current_date = date(2026, 7, 17)

    # When: getting coverage status
    status = calendar.get_coverage_status(current_date)

    # Then: all metadata present
    assert status["version"] == "hnx-vnx-2026-1403-1517"
    assert status["valid_from"] == "2026-01-01"
    assert status["valid_through"] == "2026-12-31"
    assert len(status["sources"]) == 2
    assert status["current_date"] == "2026-07-17"
    assert status["days_remaining"] > 150
    assert status["is_expired"] is False
    assert status["near_expiry"] is False
    assert status["status"] == "OK"


def test_coverage_status_shows_warning_when_near_expiry() -> None:
    # Given: a date near expiry
    calendar = VietnamSessionCalendar()
    current_date = date(2026, 11, 15)  # 46 days remaining

    # When: getting status
    status = calendar.get_coverage_status(current_date)

    # Then: warning status
    assert status["status"] == "WARNING"
    assert status["near_expiry"] is True
    assert status["is_expired"] is False
    assert status["days_remaining"] == 46


def test_coverage_status_shows_expired_after_valid_through() -> None:
    # Given: a date after validity period
    calendar = VietnamSessionCalendar()
    current_date = date(2027, 1, 15)

    # When: getting status
    status = calendar.get_coverage_status(current_date)

    # Then: expired status
    assert status["status"] == "EXPIRED"
    assert status["is_expired"] is True
    assert status["days_remaining"] == 0


def test_latest_session_fails_for_date_beyond_valid_through() -> None:
    # Given: a date beyond calendar validity
    calendar = VietnamSessionCalendar()
    future_date = date(2027, 2, 1)

    # When: attempting to resolve session
    # Then: coverage error with actionable message
    with pytest.raises(CalendarCoverageError) as exc_info:
        calendar.latest_session_on_or_before(future_date)

    assert "does not cover" in str(exc_info.value)
    assert "2026-01-01 through 2026-12-31" in str(exc_info.value)
    assert "Update the calendar" in str(exc_info.value)


def test_latest_session_fails_for_date_before_valid_from() -> None:
    # Given: a date before calendar validity
    calendar = VietnamSessionCalendar()
    past_date = date(2025, 12, 1)

    # When: attempting to resolve session
    # Then: coverage error
    with pytest.raises(CalendarCoverageError) as exc_info:
        calendar.latest_session_on_or_before(past_date)

    assert "does not cover" in str(exc_info.value)


def test_calendar_works_normally_within_validity() -> None:
    # Given: a date within validity
    calendar = VietnamSessionCalendar()
    valid_date = date(2026, 7, 17)  # Friday

    # When: using calendar functions
    is_session = calendar.is_session(valid_date)
    latest = calendar.latest_session_on_or_before(valid_date)

    # Then: normal operation
    assert is_session is True
    assert latest == valid_date


def test_is_session_does_not_enforce_coverage() -> None:
    # Given: a date beyond validity that would be a weekday
    calendar = VietnamSessionCalendar()
    future_date = date(2027, 7, 16)  # Friday

    # When: checking if it's a session (method doesn't enforce coverage)
    is_session = calendar.is_session(future_date)

    # Then: returns weekday result (but should not be relied upon)
    # Note: is_session is a simple weekday check; coverage enforcement
    # is in latest_session_on_or_before and _ensure_covered
    assert is_session is True  # Friday, not a configured holiday


def test_coverage_error_message_includes_update_instructions() -> None:
    # Given: the current calendar
    calendar = VietnamSessionCalendar()

    # When: triggering coverage error
    with pytest.raises(CalendarCoverageError) as exc_info:
        calendar._ensure_covered(date(2028, 1, 1))

    # Then: error includes update guidance
    error_msg = str(exc_info.value)
    assert "Update the calendar with official holiday data" in error_msg
    assert "for the operating year" in error_msg
