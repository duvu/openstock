from __future__ import annotations

import importlib.util
from types import ModuleType

import pandas as pd
import pytest

from vnstock.core.contracts import CONTRACT_REGISTRY
from vnstock.core.provider.plugin import ProviderPlugin
from vnstock.core.runtime.bootstrap import default_plugin_registry
from vnstock.providers.fiinquantx.approval import fiinquantx_license_approval
from vnstock.providers.fiinquantx.bridge import FiinQuantXSDK, FiinQuantXState
from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXLicenseNotAcknowledgedError,
    FiinQuantXNotInstalledError,
)
from vnstock.providers.fiinquantx.plugin import FiinQuantXProviderPlugin


def _approve_runtime(monkeypatch) -> None:
    monkeypatch.setenv("VNSTOCK_FIINQUANTX_LICENSED", "true")
    monkeypatch.setenv("VNSTOCK_FIINQUANTX_LICENSE_APPROVAL_REF", "LEGAL-2026-001")


def test_default_registry_constructs_without_fiinquantx() -> None:
    registry = default_plugin_registry()

    assert "FIINQUANTX" in registry.names()
    assert importlib.util.find_spec("fiinquantx") is None


def test_fiinquantx_is_fail_closed_until_runtime_evidence() -> None:
    registry = default_plugin_registry()
    plugin = registry.get("FIINQUANTX")

    capabilities = plugin.capabilities()

    assert capabilities
    assert all(not item["supported"] for item in capabilities.values())
    assert all(item["status"] == "unsupported" for item in capabilities.values())
    with pytest.raises(FiinQuantXNotInstalledError):
        plugin.fetch("equity.ohlcv", {"symbol": "FPT"})


def test_fiinquantx_conforms_to_provider_plugin() -> None:
    plugin = default_plugin_registry().get("FIINQUANTX")

    assert isinstance(plugin, ProviderPlugin)


def test_fiinquantx_does_not_expose_forbidden_sdk_surfaces() -> None:
    from vnstock.providers.fiinquantx.policy import FORBIDDEN_MEMBER_NAMES

    assert "order" in FORBIDDEN_MEMBER_NAMES
    assert "positions" in FORBIDDEN_MEMBER_NAMES
    assert "account" in FORBIDDEN_MEMBER_NAMES
    assert "Fetch_Trading_Data" not in FORBIDDEN_MEMBER_NAMES


def test_fiinquantx_normalizes_licensed_equity_ohlcv(monkeypatch) -> None:
    class FakeEvent:
        def get_data(self) -> pd.DataFrame:
            frame = pd.DataFrame(
                {
                    "ticker": ["VCB"],
                    "timestamp": ["2026-07-14"],
                    "open": [100.0],
                    "high": [102.0],
                    "low": [99.0],
                    "close": [101.0],
                    "volume": [200.0],
                    "value": [20200.0],
                    "unverified_field": [1.0],
                }
            )
            frame.attrs["session_id"] = "not-logged"
            return frame

    class FakeSession:
        def Fetch_Trading_Data(self, **_kwargs) -> FakeEvent:
            return FakeEvent()

        def TickerList(self, **_kwargs) -> list[str]:
            return ["VCB", "VIC"]

    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            pass

        def login(self) -> FakeSession:
            return FakeSession()

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    _approve_runtime(monkeypatch)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    result = FiinQuantXProviderPlugin().fetch("equity.ohlcv", {"symbol": "VCB"})

    assert list(result.columns) == [
        "symbol",
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "value",
    ]
    assert result.loc[0, "symbol"] == "VCB"
    assert pd.api.types.is_datetime64_any_dtype(result["time"])
    assert result.attrs["provider"] == "FIINQUANTX"
    assert "session_id" not in result.attrs


def test_fiinquantx_normalizes_current_membership_snapshot(monkeypatch) -> None:
    class FakeSession:
        def TickerList(self, **_kwargs) -> list[str]:
            return ["VCB", "VIC"]

    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            pass

        def login(self) -> FakeSession:
            return FakeSession()

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    _approve_runtime(monkeypatch)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    result = FiinQuantXProviderPlugin().fetch(
        "reference.index_membership_snapshot",
        {"symbol": "VN30"},
    )

    assert list(result.columns) == ["entity_id", "member_symbol", "observed_at"]
    assert result["member_symbol"].tolist() == ["VCB", "VIC"]
    assert pd.api.types.is_datetime64_any_dtype(result["observed_at"])
    assert result.attrs["snapshot_semantics"] == "observed_current_membership"


def test_membership_snapshot_contracts_are_registered() -> None:
    index_contract = CONTRACT_REGISTRY.get("reference.index_membership_snapshot")
    sector_contract = CONTRACT_REGISTRY.get("reference.sector_membership_snapshot")

    assert index_contract.required_columns == [
        "entity_id",
        "member_symbol",
        "observed_at",
    ]
    assert sector_contract.required_columns == index_contract.required_columns


def test_fiinquantx_rejects_unbounded_history_before_session_login(monkeypatch) -> None:
    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            pass

        def login(self) -> None:
            raise AssertionError("session login must not be called")

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    _approve_runtime(monkeypatch)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    with pytest.raises(ValueError, match="count_back"):
        FiinQuantXProviderPlugin().fetch(
            "equity.ohlcv",
            {"symbol": "VCB", "count_back": 0},
        )


def test_fiinquantx_requires_license_acknowledgement_before_login(monkeypatch) -> None:
    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("session factory must not be called")

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    monkeypatch.delenv("VNSTOCK_FIINQUANTX_LICENSED", raising=False)
    monkeypatch.delenv("VNSTOCK_FIINQUANTX_LICENSE_APPROVAL_REF", raising=False)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    with pytest.raises(FiinQuantXLicenseNotAcknowledgedError):
        FiinQuantXProviderPlugin().fetch("equity.ohlcv", {"symbol": "VCB"})


def test_boolean_acknowledgement_alone_cannot_create_session(monkeypatch) -> None:
    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("session factory must not be called")

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    monkeypatch.setenv("VNSTOCK_FIINQUANTX_LICENSED", "true")
    monkeypatch.delenv("VNSTOCK_FIINQUANTX_LICENSE_APPROVAL_REF", raising=False)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    approval = fiinquantx_license_approval()

    assert approval.acknowledged is True
    assert approval.approved is False
    assert approval.reference_fingerprint is None
    with pytest.raises(FiinQuantXLicenseNotAcknowledgedError):
        FiinQuantXProviderPlugin().fetch("equity.ohlcv", {"symbol": "VCB"})


@pytest.mark.parametrize("reference", ["pending", "TBD", "bad reference", "x"])
def test_placeholder_or_malformed_license_reference_is_rejected(
    monkeypatch, reference
) -> None:
    monkeypatch.setenv("VNSTOCK_FIINQUANTX_LICENSED", "true")
    monkeypatch.setenv("VNSTOCK_FIINQUANTX_LICENSE_APPROVAL_REF", reference)

    assert fiinquantx_license_approval().approved is False


def test_fiinquantx_capabilities_require_credentials(monkeypatch) -> None:
    module = ModuleType("FiinQuantX")
    _approve_runtime(monkeypatch)
    monkeypatch.delenv("FIINQUANT_USERNAME", raising=False)
    monkeypatch.delenv("FIINQUANT_PASSWORD", raising=False)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    capabilities = FiinQuantXProviderPlugin().capabilities()

    assert all(not capability["supported"] for capability in capabilities.values())
    assert capabilities["equity.ohlcv"]["status"] == "unsupported"


def test_fiinquantx_diagnostics_redact_approval_reference(monkeypatch) -> None:
    module = ModuleType("FiinQuantX")
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    _approve_runtime(monkeypatch)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    diagnostics = FiinQuantXProviderPlugin().diagnostics()

    assert diagnostics["licensed_runtime_approved"] is True
    assert diagnostics["license_approval_reference_configured"] is True
    assert diagnostics["license_approval_reference_fingerprint"]
    assert "LEGAL-2026-001" not in str(diagnostics)


@pytest.mark.parametrize(
    ("params", "error_pattern"),
    [
        ({"symbol": "VCB", "adjusted": "false"}, "Unsupported FiinQuantX parameters"),
        ({"symbol": "VCB", "lasted": "true"}, "Unsupported FiinQuantX parameters"),
        ({"symbol": "VCB", "start": "2026-07-01"}, "requires 'end'"),
    ],
)
def test_fiinquantx_rejects_unverified_or_unbounded_controls_before_login(
    monkeypatch, params, error_pattern
) -> None:
    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            pass

        def login(self) -> None:
            raise AssertionError("session login must not be called")

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    _approve_runtime(monkeypatch)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    with pytest.raises(ValueError, match=error_pattern):
        FiinQuantXProviderPlugin().fetch("equity.ohlcv", params)


def test_fiinquantx_enforces_requested_ohlcv_row_limit(monkeypatch) -> None:
    class FakeEvent:
        def get_data(self) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "ticker": ["VCB", "VCB", "VCB"],
                    "timestamp": ["2026-07-12", "2026-07-13", "2026-07-14"],
                    "open": [100.0, 101.0, 102.0],
                    "high": [101.0, 102.0, 103.0],
                    "low": [99.0, 100.0, 101.0],
                    "close": [100.5, 101.5, 102.5],
                    "volume": [10.0, 11.0, 12.0],
                }
            )

    class FakeSession:
        def Fetch_Trading_Data(self, **_kwargs) -> FakeEvent:
            return FakeEvent()

    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            pass

        def login(self) -> FakeSession:
            return FakeSession()

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    _approve_runtime(monkeypatch)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    result = FiinQuantXProviderPlugin().fetch(
        "equity.ohlcv", {"symbol": "VCB", "count_back": 1}
    )

    assert len(result) == 1
