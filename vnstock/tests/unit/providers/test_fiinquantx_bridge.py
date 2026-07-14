from __future__ import annotations

from vnstock.providers.fiinquantx.bridge import (
    FiinQuantXState,
    load_fiinquantx_sdk,
)


def test_missing_sdk_is_reported_without_import_failure() -> None:
    result = load_fiinquantx_sdk()

    assert result.state is FiinQuantXState.NOT_INSTALLED
    assert result.module is None
    assert result.version is None
