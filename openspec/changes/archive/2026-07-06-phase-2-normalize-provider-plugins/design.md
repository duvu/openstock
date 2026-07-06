# Design: Phase 2 — Normalize Existing Providers as Internal Plugins

## Overview

Phase 2 turns existing provider integrations into internal provider plugins that comply with the Phase 1 platform contracts.

The goal is not to rewrite every provider from scratch. The goal is to put a stable adapter boundary around each provider so that later platform capabilities can be added without touching public APIs.

## Design principles

### 1. Internal normalization first

Provider plugins stay inside the monorepo in this phase.

External packages such as `vnstock-provider-tcbs` are deferred until contracts are stable.

### 2. Public API remains stable

Existing calls through `Market`, `Reference`, `Fundamental`, and `Retail` must continue to work.

### 3. Provider clients stay provider-specific

Provider-specific HTTP/session/parsing logic can stay in provider `client.py` modules.

Provider plugins own the platform boundary:

```text
provider-native payload
→ provider normalizer
→ dataset contract DataFrame
→ DataResult / DataFrame attrs
```

### 4. Capabilities must be explicit

No provider should be selected for a dataset unless it declares support for that dataset.

### 5. Limitations must be machine-readable

Known gaps such as experimental support, today-only intraday support, public unofficial endpoint status, missing fields, and unsupported intervals should be declared as provider metadata.

### 6. Data-only boundary remains mandatory

Provider plugins must not expose broker execution, order placement, account APIs, portfolio APIs, trading signals, or recommendations.

## Target provider layout

```text
vnstock/providers/
├── kbs/
│   ├── __init__.py
│   ├── plugin.py
│   ├── client.py
│   ├── normalize.py
│   ├── capabilities.py
│   └── fixtures/
├── vci/
├── dnse/
├── tcbs/
├── fmarket/
├── msn/
└── fmp/
```

## ProviderPlugin implementation pattern

Each provider should expose a plugin class:

```python
class TCBSProviderPlugin:
    name = "TCBS"

    def capabilities(self) -> dict:
        return TCBS_CAPABILITIES

    def validate_params(self, dataset: str, params: dict) -> None:
        ...

    def fetch(self, dataset: str, params: dict) -> pd.DataFrame:
        handler = self._dataset_handlers.get(dataset)
        if handler is None:
            raise UnsupportedDatasetForProviderError(dataset, self.name)
        return handler(params)

    def diagnostics(self) -> dict:
        return {
            "provider": self.name,
            "limitations": TCBS_LIMITATIONS,
        }
```

## Dataset handler mapping

Provider plugins should define a canonical dataset map:

```python
_dataset_handlers = {
    "equity.ohlcv": self._fetch_equity_ohlcv,
    "equity.quote": self._fetch_equity_quote,
    "reference.company_info": self._fetch_company_info,
    "fundamental.balance_sheet": self._fetch_balance_sheet,
}
```

This prevents public UI code from knowing provider-specific method names.

## Capability declaration model

Capability declarations should be plain Python data in Phase 2.

Example:

```python
TCBS_CAPABILITIES = {
    "equity.ohlcv": {
        "supported": True,
        "status": "experimental",
        "auth_required": False,
        "intervals": ["1D"],
        "notes": "Unofficial public endpoint; not default provider.",
    },
    "equity.quote": {
        "supported": True,
        "status": "experimental",
        "auth_required": False,
        "notes": "Schema may differ from KBS/VCI/DNSE.",
    },
    "fundamental.balance_sheet": {
        "supported": True,
        "status": "partial",
        "auth_required": False,
        "notes": "Contract validation to be expanded in later phases.",
    },
}
```

Allowed status values:

```text
stable
experimental
partial
deprecated
unsupported
```

## Provider limitations model

Provider limitations should be structured enough for docs, diagnostics, and future routing.

Example:

```python
TCBS_LIMITATIONS = {
    "provider_status": "unofficial_public_endpoint",
    "known_limitations": [
        "not default provider",
        "schema drift risk",
        "fundamental contracts not fully validated yet",
    ],
    "excluded_capabilities": [
        "broker.login",
        "broker.order",
        "broker.account",
        "portfolio.management",
    ],
}
```

## Normalization boundary

Provider clients may return raw JSON or provider-shaped `DataFrame` objects.

Provider normalizers must return canonical `DataFrame` objects matching dataset contracts.

Example:

```text
TCBS client response
→ normalize_equity_ohlcv()
→ columns: symbol, time, open, high, low, close, volume
```

Rules:

- provider-specific fields may be kept only as optional columns or metadata;
- required dataset columns must be present;
- time columns must be parseable;
- provider name should be attached in metadata or optional column where appropriate;
- normalizers must not hide contract violations silently.

## Provider fixtures

Each provider should have offline fixtures for core supported datasets.

Fixture categories:

```text
valid response
empty but valid response
invalid symbol
suspended symbol
newly listed symbol
non-trading day
missing optional fields
unexpected extra fields
schema drift sample
```

Suggested path:

```text
vnstock/providers/tcbs/fixtures/equity_ohlcv_valid.json
vnstock/providers/tcbs/fixtures/equity_ohlcv_empty.json
vnstock/providers/tcbs/fixtures/equity_quote_valid.json
```

## Contract tests

Provider contract tests should verify:

- provider declares required capabilities;
- provider rejects unsupported datasets;
- fixture normalization matches dataset contract;
- output has required columns;
- diagnostics include provider limitations;
- out-of-scope capabilities are not exposed.

Suggested path:

```text
tests/contracts/providers/test_tcbs_provider_contract.py
tests/contracts/providers/test_kbs_provider_contract.py
tests/contracts/providers/test_vci_provider_contract.py
tests/contracts/providers/test_dnse_provider_contract.py
```

## Capability matrix generation

The provider registry should generate a matrix from declared capabilities.

Example output:

```python
{
    "equity.ohlcv": {
        "KBS": {"supported": True, "status": "stable"},
        "VCI": {"supported": True, "status": "stable"},
        "DNSE": {"supported": True, "status": "stable"},
        "TCBS": {"supported": True, "status": "experimental"},
    }
}
```

The matrix should be deterministic and testable.

## Migration strategy

### Step 1

Add plugin wrappers around current provider implementations without changing public APIs.

### Step 2

Register provider plugins in the internal registry.

### Step 3

Move one dataset path per provider through the plugin boundary, starting with `equity.ohlcv`.

### Step 4

Add fixtures and contract tests for adapted paths.

### Step 5

Repeat for quote, intraday, reference, fundamental, and fund datasets.

## Error model

Provider normalization should use Phase 1 platform errors where possible:

```text
ProviderNotFoundError
UnsupportedDatasetError
UnsupportedDatasetForProviderError
ProviderFetchError
DatasetContractError
```

Additional provider-specific exceptions may be wrapped in `ProviderFetchError`.

## Open questions

1. Should provider capabilities live in Python modules or YAML files?
2. Should fixtures store raw provider payloads, normalized frames, or both?
3. Should provider limitations be included in package docs automatically?
4. Should unstable providers be disabled from `source="auto"` by default until Phase 3?
5. Should `pyproject.toml` product description be narrowed to match data-only positioning in a separate change?
