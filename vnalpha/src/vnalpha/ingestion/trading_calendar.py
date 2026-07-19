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


class CalendarCoverageError(ValueError):
    pass


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
    valid_from: date = date(2026, 1, 1)
    valid_through: date = date(2026, 12, 31)

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

    def latest_session_on_or_before(self, market_date: date) -> date:
        """Return the latest configured session on or before a market date."""
        self._ensure_covered(market_date)
        current_date = market_date
        while not self.is_session(current_date):
            current_date -= timedelta(days=1)
            if current_date < self.valid_from:
                raise CalendarCoverageError(
                    "Vietnam trading calendar has no configured prior session for "
                    f"{market_date.isoformat()}."
                )
        return current_date

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

    def is_near_expiry(self, current_date: date, warning_days: int = 90) -> bool:
        """Return whether the calendar is approaching its validity horizon.

        Args:
            current_date: The current operating date.
            warning_days: Days before expiry to start warning (default 90).

        Returns:
            True if within warning_days of valid_through, False otherwise.
        """
        days_remaining = (self.valid_through - current_date).days
        return 0 <= days_remaining <= warning_days

    def get_coverage_status(self, current_date: date) -> dict[str, object]:
        """Return calendar coverage metadata for operational visibility.

        Returns:
            Dictionary with version, valid range, sources, and expiry status.
        """
        days_remaining = (self.valid_through - current_date).days
        is_expired = current_date > self.valid_through
        near_expiry = self.is_near_expiry(current_date)

        return {
            "version": self.version,
            "valid_from": self.valid_from.isoformat(),
            "valid_through": self.valid_through.isoformat(),
            "sources": list(self.sources),
            "current_date": current_date.isoformat(),
            "days_remaining": days_remaining if not is_expired else 0,
            "is_expired": is_expired,
            "near_expiry": near_expiry,
            "status": (
                "EXPIRED" if is_expired
                else "WARNING" if near_expiry
                else "OK"
            ),
        }

    def _ensure_covered(self, market_date: date) -> None:
        if not self.valid_from <= market_date <= self.valid_through:
            raise CalendarCoverageError(
                "Vietnam trading calendar does not cover "
                f"{market_date.isoformat()}; supported range is "
                f"{self.valid_from.isoformat()} through {self.valid_through.isoformat()}. "
                "Update the calendar with official holiday data for the operating year."
            )
