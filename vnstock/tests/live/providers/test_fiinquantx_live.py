from __future__ import annotations

import pandas as pd
import pytest

from tests.live.conftest import skip_if_provider_excluded
from vnstock.providers.fiinquantx.approval import fiinquantx_license_approval
from vnstock.providers.fiinquantx.plugin import FiinQuantXProviderPlugin

pytestmark = [pytest.mark.live, pytest.mark.provider]

_APPROVED = fiinquantx_license_approval().approved


@skip_if_provider_excluded("FIINQUANTX")
@pytest.mark.skipif(
    not _APPROVED,
    reason="Set VNSTOCK_FIINQUANTX_LICENSED=true.",
)
class TestFiinQuantXLive:
    def test_bounded_equity_ohlcv_has_canonical_schema(self) -> None:
        result = FiinQuantXProviderPlugin().fetch(
            "equity.ohlcv", {"symbol": "VCB", "count_back": 2}
        )

        assert isinstance(result, pd.DataFrame)
        assert 1 <= len(result) <= 2
        assert {"symbol", "time", "open", "high", "low", "close", "volume"} <= set(
            result.columns
        )
        assert result.attrs["provider"] == "FIINQUANTX"

    def test_current_index_membership_has_snapshot_schema(self) -> None:
        result = FiinQuantXProviderPlugin().fetch(
            "reference.index_membership_snapshot", {"symbol": "VN30"}
        )

        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert list(result.columns) == ["entity_id", "member_symbol", "observed_at"]
        assert result.attrs["snapshot_semantics"] == "observed_current_membership"
