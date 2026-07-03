# Design: Phase 1 — Core Contracts and Internal Plugin Foundation

## Overview

This change introduces the internal abstractions required for a plugin-based `vnstock` architecture.

The design intentionally keeps the public API stable while adding a structured internal execution path.

## Design principles

### 1. Public API compatibility first

Existing user code should not break.

Public API example that must continue working:

```python
from vnstock import Market

market = Market()

bars = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2026-07-03",
    interval="1D",
    validate=True,
)
```

### 2. Contracts before plugins

Dataset contracts must exist before external plugin packages are introduced.

Provider plugins must normalize data to dataset contracts.

### 3. Internal plugins before external packages

Phase 1 introduces internal plugin architecture only.

External packages such as `vnstock-provider-tcbs` or `vnstock-provider-vci` are explicitly out of scope.

### 4. Metadata-rich internal result

Platform internals should use structured metadata:

- dataset;
- provider;
- quality status;
- validation report;
- diagnostics;
- fetched timestamp;
- ingestion run ID, if available.

### 5. Data-only boundary

The architecture must not introduce trading analysis, recommendation, portfolio, broker login, account APIs, or order execution.

## Core components

## 1. Dataset contracts

### Purpose

Dataset contracts define the canonical shape of supported datasets.

They answer:

```text
What dataset is this?
Which columns are required?
Which columns are optional?
What dtypes are expected?
Which validator should run?
Which providers support it?
```

### Suggested module layout

```text
vnstock/core/contracts/
├── __init__.py
├── base.py
├── registry.py
├── equity.py
├── index.py
├── reference.py
├── fundamental.py
├── fund.py
└── foreign_flow.py
```

### Base contract model

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetContract:
    dataset: str
    required_columns: list[str]
    optional_columns: list[str] = field(default_factory=list)
    dtype_rules: dict[str, Any] = field(default_factory=dict)
    time_column: str | None = None
    symbol_column: str | None = "symbol"
    validator: str | None = None
    description: str | None = None
```

### Example: OHLCV contract

```python
OHLCV_CONTRACT = DatasetContract(
    dataset="equity.ohlcv",
    required_columns=[
        "symbol",
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ],
    optional_columns=[
        "value",
        "provider",
        "fetched_at",
        "adjusted",
    ],
    dtype_rules={
        "symbol": "string",
        "time": "datetime64[ns]",
        "open": "float64",
        "high": "float64",
        "low": "float64",
        "close": "float64",
        "volume": "float64",
    },
    time_column="time",
    symbol_column="symbol",
    validator="ohlcv",
    description="Daily or intraday OHLCV bars for equity instruments.",
)
```

### Contract registry

```python
class DatasetContractRegistry:
    def register(self, contract: DatasetContract) -> None:
        ...

    def get(self, dataset: str) -> DatasetContract:
        ...

    def list(self) -> list[DatasetContract]:
        ...
```

## 2. ProviderPlugin interface

### Purpose

A provider plugin encapsulates one data source.

It should expose:

- provider name;
- capabilities;
- fetch behavior;
- parameter validation;
- diagnostics.

### Suggested module

```text
vnstock/core/provider/plugin.py
```

### Interface

```python
from typing import Protocol, Any
import pandas as pd


class ProviderPlugin(Protocol):
    name: str

    def capabilities(self) -> dict[str, Any]:
        ...

    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame:
        ...

    def validate_params(self, dataset: str, params: dict[str, Any]) -> None:
        ...

    def diagnostics(self) -> dict[str, Any]:
        ...
```

### Capability format

```python
{
    "equity.ohlcv": {
        "supported": True,
        "intervals": ["1D", "1W", "1M"],
        "auth_required": False,
        "status": "stable",
        "notes": "Default daily OHLCV provider for Vietnamese equities."
    },
    "equity.quote": {
        "supported": True,
        "auth_required": False,
        "status": "stable"
    }
}
```

Capability `status` values:

```text
stable
experimental
partial
deprecated
unsupported
```

## 3. ProviderRegistry

### Purpose

The registry keeps track of available providers and finds candidates for a dataset.

### Suggested module

```text
vnstock/core/provider/registry.py
```

### API

```python
class ProviderRegistry:
    def register(self, provider: ProviderPlugin) -> None:
        ...

    def get(self, name: str) -> ProviderPlugin:
        ...

    def providers_for(self, dataset: str) -> list[ProviderPlugin]:
        ...

    def names(self) -> list[str]:
        ...

    def capability_matrix(self) -> dict:
        ...
```

### Behavior

- Provider names should be normalized case-insensitively.
- Duplicate provider names should raise a clear error.
- Unsupported datasets should return empty candidates, not fail unexpectedly.
- `capability_matrix()` should be deterministic for tests.

## 4. ProviderRouter skeleton

### Purpose

The router resolves a dataset request to a provider.

Phase 1 only needs compatibility behavior. Later phases will add:

- health-aware routing;
- auth-aware routing;
- fallback;
- cooldown;
- rate limits.

### Suggested module

```text
vnstock/core/provider/router.py
```

### API

```python
class ProviderRouter:
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    def resolve(
        self,
        dataset: str,
        source: str | None = None,
        params: dict | None = None,
    ) -> ProviderPlugin:
        ...
```

### Phase 1 routing behavior

```text
If source is explicit:
  return that provider if it supports the dataset.
  otherwise raise UnsupportedDatasetForProvider.

If source is None or "auto":
  use configured/default provider priority.
  return first provider that supports the dataset.
```

### Future-compatible diagnostics

Router should produce a routing diagnostics object, even if simple in Phase 1:

```python
{
    "dataset": "equity.ohlcv",
    "source": "auto",
    "selected_provider": "KBS",
    "candidate_providers": ["KBS", "VCI", "DNSE", "TCBS"],
    "routing_reason": "selected default provider priority",
}
```

## 5. DataResult

### Purpose

`DataResult` gives platform internals a stable envelope.

### Suggested module

```text
vnstock/core/result.py
```

### Model

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import pandas as pd


@dataclass
class DataResult:
    dataset: str
    provider: str
    data: pd.DataFrame
    quality_status: str | None = None
    quality_report: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    fetched_at: datetime | None = None
    ingestion_run_id: str | None = None

    def to_dataframe(self) -> pd.DataFrame:
        df = self.data
        df.attrs["dataset"] = self.dataset
        df.attrs["provider"] = self.provider
        df.attrs["quality_status"] = self.quality_status
        df.attrs["quality"] = self.quality_report
        df.attrs["diagnostics"] = self.diagnostics
        df.attrs["fetched_at"] = self.fetched_at
        df.attrs["ingestion_run_id"] = self.ingestion_run_id
        return df
```

### Secret handling

`DataResult` and `DataFrame.attrs` must not contain:

```text
password
api_key
access_token
refresh_token
cookie
session id
authorization header
```

## 6. Public UI integration

Existing public UI should remain stable.

Internally, UI methods should gradually move toward:

```text
UI method
→ build dataset + params
→ router.resolve()
→ provider.fetch()
→ validate by dataset contract
→ DataResult
→ DataFrame return
```

## Error model

Add clear internal exceptions:

```python
class VnstockPlatformError(Exception):
    pass


class DatasetContractError(VnstockPlatformError):
    pass


class ProviderNotFoundError(VnstockPlatformError):
    pass


class UnsupportedDatasetError(VnstockPlatformError):
    pass


class UnsupportedDatasetForProviderError(VnstockPlatformError):
    pass


class ProviderFetchError(VnstockPlatformError):
    pass
```

## Test strategy

### Unit tests

```text
test_dataset_contract_registry.py
test_provider_registry.py
test_provider_router.py
test_data_result.py
```

### Contract tests

```text
test_ohlcv_contract.py
test_quote_contract.py
test_intraday_contract.py
```

### Backward compatibility tests

Ensure existing calls still work or are mocked through current providers.

## Migration strategy

### Step 1

Add new modules without changing existing provider behavior.

### Step 2

Adapt one provider path, preferably `equity.ohlcv`, through the new registry/router.

### Step 3

Add compatibility tests.

### Step 4

Gradually adapt other provider paths in Phase 2.

## Open questions

1. Should public APIs eventually support `return_result=True` to return `DataResult` directly?
2. Should dataset contracts use dataclasses, Pydantic models, or lightweight dictionaries?
3. Should provider capabilities be declared in Python or YAML?
4. Should contract validation be strict by default or remain opt-in through `validate=True`?
5. Should current `df.attrs["quality"]` remain the canonical metadata path?
