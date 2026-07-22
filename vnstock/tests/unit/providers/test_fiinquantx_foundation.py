from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

from vnstock.core.contracts import CONTRACT_REGISTRY
from vnstock.core.provider.plugin import ProviderPlugin
from vnstock.core.runtime.bootstrap import default_plugin_registry
from vnstock.providers.fiinquantx.bridge import FiinQuantXSDK, FiinQuantXState
from vnstock.providers.fiinquantx.exceptions import FiinQuantXNotInstalledError
from vnstock.providers.fiinquantx.normalize import normalize_membership
from vnstock.providers.fiinquantx.plugin import FiinQuantXProviderPlugin
from vnstock.providers.fiinquantx.policy import (
    ALLOWED_MEMBER_NAMES,
    DOCUMENTED_DATASETS,
    FORBIDDEN_MEMBER_NAMES,
    IMPLEMENTED_DATASETS,
)


def test_default_registry_constructs_without_fiinquantx() -> None:
    registry = default_plugin_registry()

    assert "FIINQUANTX" in registry.names()
    assert importlib.util.find_spec("fiinquantx") is None


def test_fiinquantx_capability_inventory_owns_documented_and_implemented_states() -> (
    None
):
    inventory_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "providers"
        / "fiinquantx-capability-inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    required_fields = {
        "sdk_method",
        "sdk_version",
        "request_mode",
        "verified_signature",
        "entity_scope",
        "candidate_canonical_dataset",
        "named_consumer",
        "license_scope",
        "entitlement_state",
        "runtime_probe_state",
        "contract_state",
        "service_state",
        "persistence_state",
        "point_in_time_semantics",
        "streaming_or_sync",
        "row_request_range_limits",
        "known_units_and_signs",
        "known_revision_behavior",
        "blocking_reason",
        "evidence_reference",
    }
    synchronous_entries = [
        entry for entry in inventory["entries"] if entry["streaming_or_sync"] == "SYNC"
    ]
    inventory_members = {
        entry["sdk_method"].split(".", maxsplit=1)[0] for entry in synchronous_entries
    }
    documented_datasets = {
        entry["candidate_canonical_dataset"] for entry in synchronous_entries
    }
    implemented_datasets = {
        entry["candidate_canonical_dataset"]
        for entry in synchronous_entries
        if entry["service_state"] == "IMPLEMENTED"
    }

    assert all(required_fields <= entry.keys() for entry in inventory["entries"])
    assert inventory_members == ALLOWED_MEMBER_NAMES - {"FiinSession"}
    assert documented_datasets == DOCUMENTED_DATASETS
    assert implemented_datasets == IMPLEMENTED_DATASETS
    capabilities = FiinQuantXProviderPlugin().capabilities()
    capability_implemented_datasets = {
        dataset
        for dataset, capability in capabilities.items()
        if capability["inventory_state"] == "IMPLEMENTED"
    }

    assert set(capabilities) == documented_datasets
    assert capability_implemented_datasets == implemented_datasets


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
    assert isinstance(result["observed_at"].dtype, pd.DatetimeTZDtype)
    assert str(result["observed_at"].dt.tz) == "UTC"
    assert result.attrs["snapshot_semantics"] == "observed_current_membership"
    assert result.attrs["source_method"] == "TickerList"
    assert result.attrs["source_query"] == "VN30"


def test_fiinquantx_normalizes_empty_membership_with_contract_dtypes() -> None:
    result = normalize_membership([], "VN30")

    assert result.empty
    assert str(result["entity_id"].dtype) == "string"
    assert str(result["member_symbol"].dtype) == "string"
    assert isinstance(result["observed_at"].dtype, pd.DatetimeTZDtype)
    assert str(result["observed_at"].dt.tz) == "UTC"


def test_membership_snapshot_contracts_are_registered() -> None:
    index_contract = CONTRACT_REGISTRY.get("reference.index_membership_snapshot")
    sector_contract = CONTRACT_REGISTRY.get("reference.sector_membership_snapshot")

    assert index_contract.required_columns == [
        "entity_id",
        "member_symbol",
        "observed_at",
    ]
    assert sector_contract.required_columns == index_contract.required_columns
    assert index_contract.dtype_rules["observed_at"] == "datetime64[ns, UTC]"
    assert sector_contract.dtype_rules["observed_at"] == "datetime64[ns, UTC]"


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
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    with pytest.raises(ValueError, match="count_back"):
        FiinQuantXProviderPlugin().fetch(
            "equity.ohlcv",
            {"symbol": "VCB", "count_back": 0},
        )


def test_fiinquantx_logs_in_with_supported_sdk_and_credentials(monkeypatch) -> None:
    session_constructed = False

    class FakeSession:
        def TickerList(self, **_kwargs) -> list[str]:
            return ["VCB"]

    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            nonlocal session_constructed
            session_constructed = True

        def login(self) -> FakeSession:
            return FakeSession()

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    result = FiinQuantXProviderPlugin().fetch(
        "reference.index_membership_snapshot", {"symbol": "VN30"}
    )

    assert session_constructed is True
    assert result["member_symbol"].tolist() == ["VCB"]


def test_fiinquantx_capabilities_require_credentials(monkeypatch) -> None:
    module = ModuleType("FiinQuantX")
    monkeypatch.delenv("FIINQUANT_USERNAME", raising=False)
    monkeypatch.delenv("FIINQUANT_PASSWORD", raising=False)
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    capabilities = FiinQuantXProviderPlugin().capabilities()

    assert all(not capability["supported"] for capability in capabilities.values())
    assert capabilities["equity.ohlcv"]["status"] == "unsupported"


def test_fiinquantx_diagnostics_report_runtime_evidence(monkeypatch) -> None:
    module = ModuleType("FiinQuantX")
    monkeypatch.setenv("FIINQUANT_USERNAME", "configured-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "configured-password")
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    diagnostics = FiinQuantXProviderPlugin().diagnostics()

    assert diagnostics["state"] == "INSTALLED_SUPPORTED"


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
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )

    result = FiinQuantXProviderPlugin().fetch(
        "equity.ohlcv", {"symbol": "VCB", "count_back": 1}
    )

    assert len(result) == 1
