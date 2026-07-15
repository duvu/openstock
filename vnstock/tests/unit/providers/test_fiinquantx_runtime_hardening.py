from __future__ import annotations

from types import ModuleType

import pandas as pd
import pytest

from vnstock.providers.fiinquantx.bridge import FiinQuantXSDK, FiinQuantXState
from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXAuthenticationError,
    FiinQuantXEntitlementError,
    FiinQuantXRateLimitError,
    map_fiinquantx_exception,
)
from vnstock.providers.fiinquantx.plugin import FiinQuantXProviderPlugin
from vnstock.providers.fiinquantx.session import reset_fiinquantx_runtime_state


@pytest.fixture(autouse=True)
def _reset_runtime_state() -> None:
    reset_fiinquantx_runtime_state()
    yield
    reset_fiinquantx_runtime_state()


def _configure(monkeypatch, module: ModuleType) -> None:
    monkeypatch.setenv("FIINQUANT_USERNAME", "u")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "p")
    monkeypatch.setenv("VNSTOCK_FIINQUANTX_LICENSED", "true")
    monkeypatch.setattr(
        "vnstock.providers.fiinquantx.plugin.load_fiinquantx_sdk",
        lambda: FiinQuantXSDK(FiinQuantXState.INSTALLED_SUPPORTED, module, "0.1.64"),
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["VCB", "VCB", "VCB"],
            "timestamp": ["2026-07-01", "2026-07-02", "2026-07-03"],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [10.0, 11.0, 12.0],
            "value": [1005.0, 1116.5, 1230.0],
        }
    )


def test_date_range_is_bounded_and_forwarded_without_period(monkeypatch) -> None:
    requests: list[dict] = []

    class FakeEvent:
        def get_data(self) -> pd.DataFrame:
            return _frame()

    class FakeSession:
        def Fetch_Trading_Data(self, **kwargs):
            requests.append(kwargs)
            return FakeEvent()

    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            pass

        def login(self) -> FakeSession:
            return FakeSession()

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    _configure(monkeypatch, module)

    result = FiinQuantXProviderPlugin().fetch(
        "equity.ohlcv",
        {
            "symbol": "VCB",
            "start": "2026-07-02",
            "end": "2026-07-03",
            "interval": "1D",
        },
    )

    assert result["time"].dt.date.astype(str).tolist() == ["2026-07-02", "2026-07-03"]
    assert requests[0]["from_date"] == "2026-07-02"
    assert requests[0]["to_date"] == "2026-07-03"
    assert "period" not in requests[0]
    assert result.attrs["ohlcv_request_policy"]["mode"] == "date_range"


def test_open_ended_date_range_fails_before_login(monkeypatch) -> None:
    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            raise AssertionError("session construction must not be attempted")

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    _configure(monkeypatch, module)

    with pytest.raises(ValueError, match="requires 'end'"):
        FiinQuantXProviderPlugin().fetch(
            "equity.ohlcv", {"symbol": "VCB", "start": "2026-07-01"}
        )


def test_session_is_reused_within_ttl(monkeypatch) -> None:
    session_count = 0

    class FakeEvent:
        def get_data(self) -> pd.DataFrame:
            return _frame().iloc[:1]

    class FakeSession:
        def Fetch_Trading_Data(self, **_kwargs):
            return FakeEvent()

    class FakeFiinSession:
        def __init__(self, **_kwargs) -> None:
            pass

        def login(self) -> FakeSession:
            nonlocal session_count
            session_count += 1
            return FakeSession()

    module = ModuleType("FiinQuantX")
    module.FiinSession = FakeFiinSession
    _configure(monkeypatch, module)

    plugin = FiinQuantXProviderPlugin()
    plugin.fetch("equity.ohlcv", {"symbol": "VCB", "count_back": 1})
    plugin.fetch("equity.ohlcv", {"symbol": "VCB", "count_back": 1})

    assert session_count == 1
    diagnostics = plugin.diagnostics()["runtime"]
    assert diagnostics["session_cached"] is True
    assert diagnostics["max_concurrency"] == 1


@pytest.mark.parametrize(
    ("message", "expected_type"),
    [
        ("session expired", FiinQuantXAuthenticationError),
        ("subscription does not allow this dataset", FiinQuantXEntitlementError),
        ("HTTP 429 rate limit", FiinQuantXRateLimitError),
    ],
)
def test_vendor_failures_map_to_stable_typed_errors(message, expected_type) -> None:
    mapped = map_fiinquantx_exception(RuntimeError(message), "equity.ohlcv")

    assert isinstance(mapped, expected_type)
    assert message not in str(mapped)
    assert mapped.vendor_exception_type == "RuntimeError"
