from __future__ import annotations

import pandas as pd
import pytest

from vnstock.core.provider.exceptions import ProviderFetchError
from vnstock.core.provider.health import HealthStatus, InMemoryProviderHealthStore
from vnstock.core.provider.plugin_registry import PluginRegistry
from vnstock.core.runtime.plugin_runtime import PluginRuntime
from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXAuthenticationError,
    FiinQuantXRateLimitError,
    FiinQuantXSchemaError,
)

_DATASET = "equity.ohlcv"


class _FailingProvider:
    name = "FIINQUANTX"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def capabilities(self):
        return {_DATASET: {"supported": True}}

    def validate_params(self, dataset, params):
        del dataset, params

    def fetch(self, dataset, params):
        del dataset, params
        raise self.error

    def diagnostics(self):
        return {}


class _SuccessfulProvider(_FailingProvider):
    def fetch(self, dataset, params):
        del dataset, params
        return pd.DataFrame({"symbol": ["FPT"], "time": ["2026-07-01"]})


def _runtime(error: Exception) -> tuple[PluginRuntime, InMemoryProviderHealthStore]:
    registry = PluginRegistry()
    registry.register(_FailingProvider(error))
    health = InMemoryProviderHealthStore()
    return PluginRuntime(registry, health_store=health), health


def test_authentication_failure_does_not_poison_provider_health() -> None:
    runtime, health = _runtime(FiinQuantXAuthenticationError(_DATASET))

    with pytest.raises(FiinQuantXAuthenticationError):
        runtime.fetch(_DATASET, {"symbol": "FPT"}, source="FIINQUANTX")

    snapshot = health.get("FIINQUANTX", _DATASET)
    assert snapshot.status is HealthStatus.UNKNOWN
    assert snapshot.failure_count == 0
    assert snapshot.cooldown_until is None


def test_rate_limit_enters_immediate_bounded_cooldown() -> None:
    runtime, health = _runtime(FiinQuantXRateLimitError(_DATASET))

    with pytest.raises(FiinQuantXRateLimitError):
        runtime.fetch(_DATASET, {"symbol": "FPT"}, source="FIINQUANTX")

    snapshot = health.get("FIINQUANTX", _DATASET)
    assert snapshot.status is HealthStatus.FAILING
    assert snapshot.failure_count == 1
    assert snapshot.is_in_cooldown()
    assert snapshot.notes == "typed_provider_failure:rate_limit"


def test_schema_failure_degrades_provider_health() -> None:
    runtime, health = _runtime(FiinQuantXSchemaError(_DATASET))

    with pytest.raises(FiinQuantXSchemaError):
        runtime.fetch(_DATASET, {"symbol": "FPT"}, source="FIINQUANTX")

    snapshot = health.get("FIINQUANTX", _DATASET)
    assert snapshot.status is HealthStatus.DEGRADED
    assert snapshot.failure_count == 1
    assert snapshot.notes == "typed_provider_failure:schema"


def test_untyped_legacy_provider_error_preserves_existing_health_behavior() -> None:
    runtime, health = _runtime(ProviderFetchError("FIINQUANTX", _DATASET))

    with pytest.raises(ProviderFetchError):
        runtime.fetch(_DATASET, {"symbol": "FPT"}, source="FIINQUANTX")

    snapshot = health.get("FIINQUANTX", _DATASET)
    assert snapshot.status is HealthStatus.DEGRADED
    assert snapshot.failure_count == 1
