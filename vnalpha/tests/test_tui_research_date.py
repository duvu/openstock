from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vnalpha.tui import research_date


def test_implicit_tui_date_uses_latest_persisted_research_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(research_date, "get_connection", lambda: connection)

    def resolve_implicit_date(
        value: str | None, *, conn: MagicMock | None = None
    ) -> str:
        assert value is None
        assert conn is connection
        return "2026-07-23"

    monkeypatch.setattr(research_date, "resolve_date", resolve_implicit_date)

    assert research_date.resolve_tui_research_date(None) == "2026-07-23"
