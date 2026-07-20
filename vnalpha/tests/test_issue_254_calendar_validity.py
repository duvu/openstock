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


def test_maintenance_fails_closed_beyond_calendar_horizon() -> None:
    # Given: a maintenance request for a date beyond the calendar horizon.
    import duckdb

    from vnalpha.maintenance.daily import (
        DailyMaintenanceRequest,
        DailyMaintenanceService,
        MaintenanceRunStatus,
    )
    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    try:
        result = DailyMaintenanceService(conn).run(
            DailyMaintenanceRequest(date="2027-03-02")  # beyond valid_through
        )
    finally:
        conn.close()

    # Then: it fails closed as NOOP with an actionable calendar warning,
    # never silently treating the future weekday as a normal session.
    assert result.status is MaintenanceRunStatus.NOOP
    assert result.mutated is False
    stage = result.stages[0]
    assert stage.name == "resolve_session"
    assert any("does not cover" in w for w in stage.warnings)
    assert any("Update the Vietnam trading calendar" in r for r in stage.remediation)


def test_maintenance_warns_near_calendar_expiry(monkeypatch) -> None:
    # Given: an in-horizon session date close to the calendar's expiry.
    import duckdb

    from vnalpha.maintenance.daily import (
        DailyMaintenanceRequest,
        DailyMaintenanceService,
    )
    from vnalpha.warehouse.migrations import run_migrations

    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    try:
        # 2026-12-30 is a Wednesday within 90 days of 2026-12-31.
        result = DailyMaintenanceService(conn).run(
            DailyMaintenanceRequest(date="2026-12-30")
        )
    finally:
        conn.close()

    session_stage = next(s for s in result.stages if s.name == "resolve_session")
    assert any("expires on 2026-12-31" in w for w in session_stage.warnings)


def test_preflight_cli_reports_calendar_version_and_validity(monkeypatch) -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    # Force the assistant route to fail fast so the CLI still emits the calendar
    # section without contacting a live provider.
    monkeypatch.setenv("VNALPHA_LLM_ENDPOINT", "http://127.0.0.1:1/v1/chat/completions")
    monkeypatch.setenv("VNALPHA_LLM_API_KEY", "")
    monkeypatch.setenv("VNALPHA_LLM_TIMEOUT", "1")
    monkeypatch.setenv("VNALPHA_LLM_MAX_RETRIES", "0")

    result = CliRunner().invoke(app, ["preflight", "--json"])

    # Preflight exits non-zero on the unavailable LLM route, but the JSON payload
    # must carry the calendar version, source-of-truth validity horizon and status.
    assert '"trading_calendar"' in result.stdout
    assert VietnamSessionCalendar().version in result.stdout
    assert "2026-12-31" in result.stdout
