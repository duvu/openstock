"""Tests for vnalpha.core.dates.resolve_date."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from vnalpha.core.dates import resolve_date

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _today_vn() -> str:
    return datetime.now(tz=_VN_TZ).strftime("%Y-%m-%d")


class TestResolveDateToday:
    def test_none_returns_today(self):
        result = resolve_date(None)
        assert result == _today_vn()
