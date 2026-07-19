"""Vietnam trading-session calendar contracts used by OHLCV maintenance."""

from dataclasses import dataclass
from datetime import date, timedelta

VIETNAM_EXCHANGE_HOLIDAYS_2026 = frozenset(
    {
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 2, 16),
        date(2026, 2, 17),
        date(2026, 2, 18),
        date(2026, 2, 19),
        date(2026, 2, 20),
        date(2026, 4, 27),
        date(2026, 4, 30),
        date(2026, 5, 1),
        date(2026, 8, 31),
        date(2026, 9, 1),
        date(2026, 9, 2),
    }
)


class InvalidSessionRangeError(ValueError):
    """Raised when a calendar session range is inverted."""


class InvalidSessionOverlapError(ValueError):
    """Raised when a requested overlap cannot include a session."""


@dataclass(frozen=True, slots=True)
class SessionRange:
    """Inclusive range of market dates to inspect."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise InvalidSessionRangeError(
                "Session range start must not be after its end."
            )


@dataclass(frozen=True, slots=True)
class VietnamSessionCalendar:
    """Versioned weekday calendar with explicit Vietnam-market holidays."""

    holidays: frozenset[date] = VIETNAM_EXCHANGE_HOLIDAYS_2026
    version: str = "hnx-vnx-2026-1403-1517"
    sources: tuple[str, str] = (
        "https://www.gov.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60021971.html",
        "https://www.gov.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60022084.html",
    )

    def sessions(self, session_range: SessionRange) -> tuple[date, ...]:
        """Return inclusive sessions, excluding weekends and configured holidays."""
        sessions: list[date] = []
        current_date = session_range.start
        while current_date <= session_range.end:
            if self.is_session(current_date):
                sessions.append(current_date)
            current_date += timedelta(days=1)
        return tuple(sessions)

    def is_session(self, market_date: date) -> bool:
        """Return whether the supplied date is a configured trading session."""
        return market_date.weekday() < 5 and market_date not in self.holidays

    def rewind_sessions(self, market_date: date, session_count: int) -> date:
        """Return the first date in an inclusive trailing session overlap."""
        if session_count < 1:
            raise InvalidSessionOverlapError("Session overlap must be at least one.")
        current_date = market_date
        remaining = session_count - 1
        while remaining > 0:
            current_date -= timedelta(days=1)
            if self.is_session(current_date):
                remaining -= 1
        return current_date
