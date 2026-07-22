from __future__ import annotations

import duckdb

from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry


def test_memory_command_returns_structured_unavailable_when_schema_is_missing(
    tmp_path,
) -> None:
    connection = duckdb.connect(":memory:")

    result = build_default_registry().execute(
        parse("/memory status"),
        conn=connection,
        root=tmp_path,
    )

    assert result.status == "PARTIAL"
    assert result.metadata == {"availability": "unavailable"}
