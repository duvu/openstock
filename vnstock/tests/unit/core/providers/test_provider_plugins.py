"""
Phase 2 provider plugin contract tests.

Tests cover:
- Capability declarations for all 7 providers
- Unsupported dataset behaviour
- Limitations metadata
- Plugin protocol conformance
- REGISTRY integration (providers_for, capability_matrix)
- Fixture normalization for core datasets
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from vnstock.core.provider.exceptions import (
    ProviderFetchError,
    UnsupportedDatasetForProviderError,
)
from vnstock.core.provider.plugin import ProviderPlugin
from vnstock.providers import REGISTRY
from vnstock.providers.dnse.normalize import (
    normalize_equity_ohlcv as dnse_normalize_ohlcv,
)
from vnstock.providers.dnse.plugin import DNSEProviderPlugin
from vnstock.providers.fmarket.plugin import FMarketProviderPlugin
from vnstock.providers.fmp.plugin import FMPProviderPlugin
from vnstock.providers.kbs.normalize import (
    normalize_equity_ohlcv as kbs_normalize_ohlcv,
)
from vnstock.providers.kbs.plugin import KBSProviderPlugin
from vnstock.providers.msn.plugin import MSNProviderPlugin
from vnstock.providers.tcbs.plugin import TCBSProviderPlugin
from vnstock.providers.vci.normalize import (
    normalize_equity_ohlcv as vci_normalize_ohlcv,
)
from vnstock.providers.vci.plugin import VCIProviderPlugin

_FIXTURE_BASE = (
    Path(__file__).parent.parent.parent.parent.parent / "vnstock" / "providers"
)


def _load_fixture(provider: str, name: str) -> dict:
    path = _FIXTURE_BASE / provider / "fixtures" / name
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kbs_ohlcv_df(rows: list[dict]) -> pd.DataFrame:
    """Build a KBS-style OHLCV DataFrame from fixture rows (after rename)."""
    if not rows:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "t": "time",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
        }
    )
    df["time"] = pd.to_datetime(df["time"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])
    return df


def _make_vci_ohlcv_df(data: dict) -> pd.DataFrame:
    """Build a VCI-style OHLCV DataFrame from fixture data (parallel arrays)."""
    if not data.get("t"):
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(data["t"], unit="s"),
            "open": pd.to_numeric(data["o"]),
            "high": pd.to_numeric(data["h"]),
            "low": pd.to_numeric(data["l"]),
            "close": pd.to_numeric(data["c"]),
            "volume": pd.to_numeric(data["v"]),
        }
    )
    return df


def _make_dnse_ohlcv_df(data: dict) -> pd.DataFrame:
    """Build a DNSE-style OHLCV DataFrame from fixture data."""
    if not data.get("t"):
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(data["t"], unit="s"),
            "open": pd.to_numeric(data["o"]),
            "high": pd.to_numeric(data["h"]),
            "low": pd.to_numeric(data["l"]),
            "close": pd.to_numeric(data["c"]),
            "volume": pd.to_numeric(data["v"]),
        }
    )
    return df


# ---------------------------------------------------------------------------
# Task 125: Capability declaration tests
# ---------------------------------------------------------------------------


class TestCapabilityDeclarations:
    """Tasks 118, 125: All providers declare capabilities correctly."""

    @pytest.mark.parametrize(
        "plugin_cls,expected_name",
        [
            (KBSProviderPlugin, "KBS"),
            (VCIProviderPlugin, "VCI"),
            (DNSEProviderPlugin, "DNSE"),
            (TCBSProviderPlugin, "TCBS"),
            (FMarketProviderPlugin, "FMARKET"),
            (MSNProviderPlugin, "MSN"),
            (FMPProviderPlugin, "FMP"),
        ],
    )
    def test_plugin_name(self, plugin_cls, expected_name):
        plugin = plugin_cls()
        assert plugin.name == expected_name

    @pytest.mark.parametrize(
        "plugin_cls",
        [
            KBSProviderPlugin,
            VCIProviderPlugin,
            DNSEProviderPlugin,
            TCBSProviderPlugin,
            FMarketProviderPlugin,
            MSNProviderPlugin,
            FMPProviderPlugin,
        ],
    )
    def test_capabilities_returns_dict(self, plugin_cls):
        plugin = plugin_cls()
        caps = plugin.capabilities()
        assert isinstance(caps, dict)
        assert len(caps) > 0

    @pytest.mark.parametrize(
        "plugin_cls",
        [
            KBSProviderPlugin,
            VCIProviderPlugin,
            DNSEProviderPlugin,
            TCBSProviderPlugin,
            FMarketProviderPlugin,
            MSNProviderPlugin,
            FMPProviderPlugin,
        ],
    )
    def test_capabilities_have_required_keys(self, plugin_cls):
        """Each capability entry must have 'supported' and 'status' keys."""
        plugin = plugin_cls()
        for dataset, cap in plugin.capabilities().items():
            assert "supported" in cap, f"{plugin.name}/{dataset} missing 'supported'"
            assert "status" in cap, f"{plugin.name}/{dataset} missing 'status'"

    def test_kbs_supports_equity_ohlcv(self):
        caps = KBSProviderPlugin().capabilities()
        assert caps["equity.ohlcv"]["supported"] is True

    def test_vci_supports_equity_ohlcv(self):
        caps = VCIProviderPlugin().capabilities()
        assert caps["equity.ohlcv"]["supported"] is True

    def test_dnse_supports_equity_ohlcv(self):
        caps = DNSEProviderPlugin().capabilities()
        assert caps["equity.ohlcv"]["supported"] is True

    def test_tcbs_requires_auth(self):
        """Task 122: TCBS requires auth for all supported datasets."""
        caps = TCBSProviderPlugin().capabilities()
        for dataset, cap in caps.items():
            if cap.get("supported"):
                assert cap.get("auth_required") is True, (
                    f"TCBS/{dataset} should require auth"
                )

    def test_fmarket_supports_fund_nav(self):
        caps = FMarketProviderPlugin().capabilities()
        assert caps["fund.nav"]["supported"] is True

    def test_msn_supports_equity_ohlcv(self):
        caps = MSNProviderPlugin().capabilities()
        assert caps["equity.ohlcv"]["supported"] is True

    def test_fmp_requires_auth(self):
        caps = FMPProviderPlugin().capabilities()
        for dataset, cap in caps.items():
            if cap.get("supported"):
                assert cap.get("auth_required") is True, (
                    f"FMP/{dataset} should require auth"
                )

    @pytest.mark.parametrize(
        "plugin_cls",
        [
            KBSProviderPlugin,
            VCIProviderPlugin,
            DNSEProviderPlugin,
            TCBSProviderPlugin,
            FMarketProviderPlugin,
            MSNProviderPlugin,
            FMPProviderPlugin,
        ],
    )
    def test_protocol_conformance(self, plugin_cls):
        """Task 119: All plugins conform to ProviderPlugin protocol."""
        plugin = plugin_cls()
        assert isinstance(plugin, ProviderPlugin)


# ---------------------------------------------------------------------------
# Task 126: Unsupported dataset behaviour
# ---------------------------------------------------------------------------


class TestUnsupportedDatasets:
    """Task 126: Unsupported datasets raise UnsupportedDatasetForProviderError."""

    def test_kbs_unsupported_raises(self):
        plugin = KBSProviderPlugin()
        with pytest.raises(UnsupportedDatasetForProviderError):
            plugin.fetch("fund.nav", {"symbol": "FPT"})

    def test_vci_unsupported_raises(self):
        plugin = VCIProviderPlugin()
        with pytest.raises(UnsupportedDatasetForProviderError):
            plugin.fetch("fund.nav", {"symbol": "FPT"})

    def test_dnse_unsupported_raises(self):
        plugin = DNSEProviderPlugin()
        with pytest.raises(UnsupportedDatasetForProviderError):
            plugin.fetch("fundamental.balance_sheet", {"symbol": "FPT"})

    def test_fmarket_unsupported_raises(self):
        plugin = FMarketProviderPlugin()
        with pytest.raises(UnsupportedDatasetForProviderError):
            plugin.fetch("equity.ohlcv", {"symbol": "FPT"})

    def test_msn_unsupported_raises(self):
        plugin = MSNProviderPlugin()
        with pytest.raises(UnsupportedDatasetForProviderError):
            plugin.fetch("fund.nav", {"symbol": "FPT"})

    def test_fmp_unsupported_fundamental_raises(self):
        """FMP declares fundamental datasets as unsupported via the plugin."""
        plugin = FMPProviderPlugin()
        with pytest.raises(UnsupportedDatasetForProviderError):
            plugin.fetch("fundamental.balance_sheet", {"symbol": "FPT"})

    def test_unknown_dataset_raises_for_all(self):
        plugins = [KBSProviderPlugin(), VCIProviderPlugin(), DNSEProviderPlugin()]
        for plugin in plugins:
            with pytest.raises(UnsupportedDatasetForProviderError):
                plugin.fetch("nonexistent.dataset", {"symbol": "FPT"})


# ---------------------------------------------------------------------------
# Task 129: Limitations metadata
# ---------------------------------------------------------------------------


class TestLimitationsMetadata:
    """Task 129: Limitations dicts exist and have required keys."""

    @pytest.mark.parametrize(
        "provider_mod,expected_keys",
        [
            (
                "vnstock.providers.kbs.capabilities",
                ["provider_status", "known_limitations", "excluded_capabilities"],
            ),
            (
                "vnstock.providers.vci.capabilities",
                ["provider_status", "known_limitations", "excluded_capabilities"],
            ),
            (
                "vnstock.providers.dnse.capabilities",
                ["provider_status", "known_limitations", "excluded_capabilities"],
            ),
            (
                "vnstock.providers.tcbs.capabilities",
                ["provider_status", "known_limitations", "excluded_capabilities"],
            ),
            (
                "vnstock.providers.fmarket.capabilities",
                ["provider_status", "known_limitations", "excluded_capabilities"],
            ),
            (
                "vnstock.providers.msn.capabilities",
                ["provider_status", "known_limitations", "excluded_capabilities"],
            ),
            (
                "vnstock.providers.fmp.capabilities",
                ["provider_status", "known_limitations", "excluded_capabilities"],
            ),
        ],
    )
    def test_limitations_declared(self, provider_mod, expected_keys):
        import importlib

        mod = importlib.import_module(provider_mod)
        limitations = getattr(
            mod, f"{provider_mod.split('.')[-2].upper()}_LIMITATIONS", None
        )
        assert limitations is not None, f"{provider_mod} missing LIMITATIONS"
        for key in expected_keys:
            assert key in limitations, f"{provider_mod} LIMITATIONS missing '{key}'"

    @pytest.mark.parametrize(
        "provider_mod",
        [
            "vnstock.providers.kbs.capabilities",
            "vnstock.providers.vci.capabilities",
            "vnstock.providers.dnse.capabilities",
            "vnstock.providers.tcbs.capabilities",
            "vnstock.providers.fmarket.capabilities",
            "vnstock.providers.msn.capabilities",
            "vnstock.providers.fmp.capabilities",
        ],
    )
    def test_data_only_boundary(self, provider_mod):
        """Task 130: broker/account capabilities marked as out of scope via excluded_capabilities."""
        import importlib

        mod = importlib.import_module(provider_mod)
        provider_name = provider_mod.split(".")[-2].upper()
        limitations = getattr(mod, f"{provider_name}_LIMITATIONS", {})
        excluded = limitations.get("excluded_capabilities", [])
        # At least one broker/account scope must be in excluded list
        broker_excluded = any(
            "broker" in cap or "account" in cap or "portfolio" in cap
            for cap in excluded
        )
        assert broker_excluded, (
            f"{provider_name} excluded_capabilities must include broker/account scope, got: {excluded}"
        )


# ---------------------------------------------------------------------------
# Task 127-128: Fixture normalization (KBS, VCI, DNSE)
# ---------------------------------------------------------------------------


class TestFixtureNormalization:
    """Tasks 127-128: Fixtures normalize to required dataset contract columns."""

    _REQUIRED_OHLCV = {"symbol", "time", "open", "high", "low", "close", "volume"}

    def test_kbs_valid_fixture_normalization(self):
        fixture = _load_fixture("kbs", "equity_ohlcv_valid.json")
        rows = fixture["data_day"]
        df = _make_kbs_ohlcv_df(rows)
        result = kbs_normalize_ohlcv(df, "FPT")
        assert set(result.columns) >= {
            "symbol",
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        assert len(result) == 3
        assert (result["symbol"] == "FPT").all()

    def test_kbs_empty_fixture_normalization(self):
        fixture = _load_fixture("kbs", "equity_ohlcv_empty.json")
        rows = fixture["data_day"]
        df = _make_kbs_ohlcv_df(rows)
        result = kbs_normalize_ohlcv(df, "FPT")
        assert len(result) == 0
        assert set(result.columns) >= {
            "symbol",
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

    def test_kbs_schema_drift_fixture_raises(self):
        """Schema drift fixture: 'o' key missing → normalize raises ProviderFetchError."""
        fixture = _load_fixture("kbs", "equity_ohlcv_schema_drift.json")
        rows = fixture["data_day"]
        # Build df without renaming 'o' → 'open' (simulating drift)
        df = pd.DataFrame(rows)
        # 'o' is absent, so 'open' won't be in df after rename
        with pytest.raises(ProviderFetchError):
            kbs_normalize_ohlcv(df, "FPT")

    def test_vci_valid_fixture_normalization(self):
        fixture = _load_fixture("vci", "equity_ohlcv_valid.json")
        data = fixture[0]  # VCI returns list of single object
        df = _make_vci_ohlcv_df(data)
        result = vci_normalize_ohlcv(df, "VCB")
        assert set(result.columns) >= {
            "symbol",
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        assert len(result) == 3
        assert (result["symbol"] == "VCB").all()

    def test_vci_empty_fixture_normalization(self):
        fixture = _load_fixture("vci", "equity_ohlcv_empty.json")
        data = fixture[0]
        df = _make_vci_ohlcv_df(data)
        result = vci_normalize_ohlcv(df, "VCB")
        assert len(result) == 0

    def test_dnse_valid_fixture_normalization(self):
        fixture = _load_fixture("dnse", "equity_ohlcv_valid.json")
        df = _make_dnse_ohlcv_df(fixture)
        result = dnse_normalize_ohlcv(df, "TCB")
        assert set(result.columns) >= {
            "symbol",
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        assert len(result) == 3
        assert (result["symbol"] == "TCB").all()


# ---------------------------------------------------------------------------
# REGISTRY integration tests
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    """Tasks 79-88, 134-141: REGISTRY has all 7 providers, correct routing."""

    def test_all_providers_registered(self):
        names = REGISTRY.names()
        assert "KBS" in names
        assert "VCI" in names
        assert "DNSE" in names
        assert "TCBS" in names
        assert "FMARKET" in names
        assert "MSN" in names
        assert "FMP" in names
        assert len(names) == 7

    def test_providers_for_equity_ohlcv(self):
        providers = REGISTRY.providers_for("equity.ohlcv")
        names = [p.name for p in providers]
        assert "KBS" in names
        assert "VCI" in names
        assert "DNSE" in names
        assert "TCBS" in names
        assert "MSN" in names
        assert "FMP" in names
        # FMarket does NOT support equity.ohlcv
        assert "FMARKET" not in names

    def test_providers_for_fund_nav(self):
        providers = REGISTRY.providers_for("fund.nav")
        assert len(providers) == 1
        assert providers[0].name == "FMARKET"

    def test_case_insensitive_get(self):
        assert REGISTRY.get("kbs") is REGISTRY.get("KBS")
        assert REGISTRY.get("VCI") is REGISTRY.get("vci")

    def test_capability_matrix_structure(self):
        """Tasks 134-141: capability_matrix() returns deterministic structured dict."""
        matrix = REGISTRY.capability_matrix()
        assert isinstance(matrix, dict)
        # Sorted by provider name
        assert list(matrix.keys()) == sorted(matrix.keys())
        # Each entry is a capabilities dict
        for _name, caps in matrix.items():
            assert isinstance(caps, dict)
            assert len(caps) > 0

    def test_capability_matrix_contains_all_providers(self):
        matrix = REGISTRY.capability_matrix()
        assert set(matrix.keys()) == {
            "DNSE",
            "FMARKET",
            "FMP",
            "KBS",
            "MSN",
            "TCBS",
            "VCI",
        }

    def test_capability_matrix_has_supported_flag(self):
        matrix = REGISTRY.capability_matrix()
        for provider_name, caps in matrix.items():
            for dataset, cap in caps.items():
                assert "supported" in cap, (
                    f"{provider_name}/{dataset} missing 'supported' in matrix"
                )
