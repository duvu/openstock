from __future__ import annotations

from collections.abc import Iterator

from vnstock.providers.fiinquantx.normalize import normalize_membership


def test_fiinquantx_normalizes_sdk_ticker_list_wrapper() -> None:
    class VendorTickerList:
        def __iter__(self) -> Iterator[str]:
            return iter(("VCB", "VIC"))

    result = normalize_membership(VendorTickerList(), "VN30")

    assert result["member_symbol"].tolist() == ["VCB", "VIC"]
