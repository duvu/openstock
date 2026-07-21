from datetime import date

from vnalpha.ingestion.trading_calendar import (
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
