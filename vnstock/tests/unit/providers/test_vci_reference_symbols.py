from __future__ import annotations

from vnstock.explorer.vci import listing as listing_module
from vnstock.providers.vci import plugin as plugin_module


def test_vci_reference_symbols_preserve_exchange_for_stock_rows(monkeypatch) -> None:
    class FakeListing:
        def __init__(self, **_kwargs) -> None:
            pass

        def all_symbols(self, **_kwargs):
            return plugin_module.pd.DataFrame(
                {"symbol": ["FPT"], "organ_name": ["FPT Corp"]}
            )

        def symbols_by_exchange(self, **_kwargs):
            return plugin_module.pd.DataFrame(
                {
                    "symbol": ["FPT", "VN30F1M"],
                    "exchange": ["HOSE", "HNX"],
                    "type": ["STOCK", "DERIVATIVE"],
                    "organ_name": ["FPT Corp", "VN30 Future"],
                }
            )

    monkeypatch.setattr(listing_module, "Listing", FakeListing)

    result = plugin_module.VCIProviderPlugin().fetch("reference.symbols", {})

    assert result[["symbol", "exchange"]].to_dict("records") == [
        {"symbol": "FPT", "exchange": "HOSE"}
    ]
