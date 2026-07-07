"""Tests for vnalpha.core.dates.resolve_date."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb
import pytest

from vnalpha.core.dates import resolve_date

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _today_vn() -> str:
    return datetime.now(tz=_VN_TZ).strftime("%Y-%m-%d")


class TestResolveDateToday:
    def test_none_returns_today(self):
        result = resolve_date(None)
        assert result == _today_vn()

    def test_today_string_returns_today(self):
        result = resolve_date("today")
        assert result == _today_vn()

    def test_today_case_insensitive(self):
        assert resolve_date("TODAY") == _today_vn()
        assert resolve_date("Today") == _today_vn()

    def test_result_is_iso_format(self):
        result = resolve_date(None)
        assert re.match(r"\d{4}-\d{2}-\d{2}", result)


class TestResolveDateIso:
    def test_valid_iso_date(self):
        assert resolve_date("2024-01-15") == "2024-01-15"

    def test_valid_iso_date_end_of_month(self):
        assert resolve_date("2024-12-31") == "2024-12-31"

    def test_valid_iso_date_leap_year(self):
        assert resolve_date("2024-02-29") == "2024-02-29"

    def test_returns_str(self):
        result = resolve_date("2024-06-01")
        assert isinstance(result, str)


class TestResolveDateErrors:
    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid date value"):
            resolve_date("15-01-2024")

    def test_nonsense_raises(self):
        with pytest.raises(ValueError):
            resolve_date("not-a-date")

    def test_partial_date_raises(self):
        with pytest.raises(ValueError):
            resolve_date("2024-01")

    def test_invalid_day_raises(self):
        with pytest.raises(ValueError):
            resolve_date("2024-02-30")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            resolve_date("")


class TestResolveDateWithConn:
    """Tests for DB-aware date resolution (task 11.3)."""

    def _make_conn(self, dates: list[str]) -> duckdb.DuckDBPyConnection:
        """Create an in-memory DB with daily_watchlist rows for given dates."""
        conn = duckdb.connect()
        conn.execute(
            """
            CREATE TABLE daily_watchlist (
                date DATE NOT NULL,
                rank INTEGER NOT NULL,
                symbol VARCHAR,
                PRIMARY KEY (date, rank)
            )
            """
        )
        for i, d in enumerate(dates):
            conn.execute(
                "INSERT INTO daily_watchlist VALUES (?, ?, 'FPT')",
                [d, i + 1],
            )
        return conn

    def test_explicit_date_is_not_affected_by_conn(self):
        """Explicit ISO date is always returned as-is regardless of DB state."""
        conn = self._make_conn(["2026-01-02"])
        assert resolve_date("2026-01-15", conn=conn) == "2026-01-15"
        conn.close()

    def test_today_with_no_data_returns_today(self):
        """If DB has no rows, returns today (Asia/Ho_Chi_Minh)."""
        conn = self._make_conn([])
        result = resolve_date(None, conn=conn)
        assert result == _today_vn()
        conn.close()

    def test_today_with_stale_data_returns_latest(self):
        """If latest data is before today, resolves to latest available date."""
        conn = self._make_conn(["2026-01-02", "2026-01-03"])
        result = resolve_date(None, conn=conn)
        # The latest date in the test DB (2026-01-03) is definitely < today
        assert result == "2026-01-03"
        conn.close()

    def test_today_without_conn_returns_vn_today(self):
        """Without conn, returns Asia/Ho_Chi_Minh today."""
        result = resolve_date("today")
        assert result == _today_vn()
