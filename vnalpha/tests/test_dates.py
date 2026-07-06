"""Tests for vnalpha.core.dates.resolve_date."""

from __future__ import annotations

import re
from datetime import date

import pytest

from vnalpha.core.dates import resolve_date


class TestResolveDateToday:
    def test_none_returns_today(self):
        result = resolve_date(None)
        assert result == str(date.today())

    def test_today_string_returns_today(self):
        result = resolve_date("today")
        assert result == str(date.today())

    def test_today_case_insensitive(self):
        assert resolve_date("TODAY") == str(date.today())
        assert resolve_date("Today") == str(date.today())

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
