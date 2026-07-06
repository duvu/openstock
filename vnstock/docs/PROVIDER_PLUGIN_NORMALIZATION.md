# Provider Plugin Normalization

This document describes the Phase 2 provider plugin system — the normalized adapter layer that wraps existing `vnstock/explorer/` and `vnstock/connector/` code with a uniform interface.

## Module Layout

Each provider lives under `vnstock/providers/<name>/`:

```
vnstock/providers/
├── __init__.py          # Global REGISTRY (PluginRegistry) + all plugin registrations
├── kbs/
│   ├── __init__.py
│   ├── capabilities.py  # KBS_CAPABILITIES + KBS_LIMITATIONS dicts
│   ├── normalize.py     # normalize_equity_ohlcv(), normalize_equity_quote()
│   ├── plugin.py        # KBSProviderPlugin (ProviderPlugin adapter)
│   └── fixtures/        # JSON fixture files for contract tests
├── vci/ ...
├── dnse/ ...
├── tcbs/ ...
├── fmarket/ ...
├── msn/ ...
└── fmp/ ...
```

## Capability Declaration Format

Each `capabilities.py` declares two module-level dicts:

### `<PROVIDER>_CAPABILITIES`

Maps dataset name → capability metadata dict.

Required keys per entry:

| Key | Type | Description |
|-----|------|-------------|
| `supported` | `bool` | Whether this provider can serve this dataset |
| `status` | `str` | One of `stable`, `experimental`, `partial`, `deprecated`, `unsupported` |
| `auth_required` | `bool` | Whether a credential is needed |
| `notes` | `str` | Human-readable notes about behaviour or limitations |

Optional keys: `intervals` (list of supported resolution strings), `schema_drift_risk`.

Example:

```python
KBS_CAPABILITIES = {
    "equity.ohlcv": {
        "supported": True,
        "status": "stable",
        "auth_required": False,
        "intervals": ["1", "5", "15", "30", "60", "D", "W", "M"],
        "notes": "Primary Vietnamese market OHLCV source.",
    },
    "fund.nav": {
        "supported": False,
        "status": "unsupported",
        "auth_required": False,
        "notes": "KBS does not provide fund NAV data.",
    },
    ...
}
```

### `<PROVIDER>_LIMITATIONS`

Documents what the provider explicitly does NOT support.

Required keys:

| Key | Type | Description |
|-----|------|-------------|
| `provider_status` | `str` | Overall endpoint stability |
| `known_limitations` | `list[str]` | Known issues or restrictions |
| `coverage_gaps` | `list[str]` | Datasets not covered |
| `schema_drift_risk` | `str` | `low`, `medium`, or `high` |
| `excluded_capabilities` | `list[str]` | Broker/account/trading scopes explicitly excluded |

Example:

```python
KBS_LIMITATIONS = {
    "provider_status": "stable_public_endpoint",
    "known_limitations": ["rate limit enforced — 20 requests/minute for guest tier"],
    "coverage_gaps": [],
    "schema_drift_risk": "low",
    "excluded_capabilities": [
        "broker.login", "broker.order", "broker.account",
        "portfolio.management", "trading.signals", "trading.recommendations",
    ],
}
```

## Dataset-to-Method Mapping

Each `plugin.py` defines a `_dataset_handlers` property that maps dataset names to internal fetch methods. These methods call the existing explorer/connector classes with lazy imports.

```python
@property
def _dataset_handlers(self):
    return {
        "equity.ohlcv": self._fetch_equity_ohlcv,
        "equity.quote": self._fetch_equity_quote,
        ...
    }
```

Unsupported datasets must raise `UnsupportedDatasetForProviderError`.

## Normalizer Contract

Each `normalize.py` exports normalizer functions. The normalizer:

1. Validates required columns are present (raises `ProviderFetchError` if missing)
2. Inserts a `symbol` column as the first column
3. Ensures `time` is `datetime64[ns]`
4. Ensures price/volume columns are numeric

Required output columns for `equity.ohlcv`:

```
symbol, time, open, high, low, close, volume
```

## Fixture Expectations

Fixtures in `vnstock/providers/<name>/fixtures/` are JSON files representing **provider-native responses** or **post-normalize DataFrames** (for providers where the explorer already normalizes output).

Fixture naming convention:

| File | Description |
|------|-------------|
| `equity_ohlcv_valid.json` | Normal data for 3–5 trading days |
| `equity_ohlcv_empty.json` | Empty response (no data) |
| `equity_ohlcv_schema_drift.json` | Response with a renamed/missing required field |
| `equity_ohlcv_auth_error.json` | Auth failure response (TCBS/FMP) |
| `equity_ohlcv_geo_restricted.json` | Geo-restriction response (DNSE) |
| `fund_nav_valid.json` | Valid fund NAV response (FMarket) |

## Contract Test Expectations

Contract tests are in `tests/unit/core/providers/test_provider_plugins.py`.

They cover:
- Protocol conformance (`isinstance(plugin, ProviderPlugin)`)
- Capability declarations (name, `supported`, `status` per dataset)
- Auth requirement flags for TCBS and FMP
- Unsupported dataset raises `UnsupportedDatasetForProviderError`
- Limitations metadata has required keys and excludes broker scope
- Fixture normalization: valid fixtures pass, schema drift fixtures raise
- REGISTRY integration: all 7 providers registered, `providers_for()`, `capability_matrix()`

## Migration Strategy

The `vnstock/providers/` package is an **additive layer**. Existing code paths are unchanged:

- `vnstock/explorer/` — legacy explorer modules, still used by UI dispatch
- `vnstock/ui/` — unchanged, routes via legacy `ProviderRegistry`
- `vnstock/api/` — legacy API adapters, unchanged

The new `REGISTRY` in `vnstock/providers/__init__.py` is a separate `PluginRegistry` instance used only when explicitly calling `REGISTRY.get(...)` or `REGISTRY.providers_for(...)`. It does not replace the legacy registry.

To route a dataset through the new plugin layer explicitly:

```python
from vnstock.providers import REGISTRY

plugin = REGISTRY.get("KBS")
df = plugin.fetch("equity.ohlcv", {"symbol": "FPT", "start": "2025-01-01", "end": "2025-06-30"})
```

## External Provider Packages

Third-party provider packages (`vnstock-provider-*`) are **deferred to a later phase** and are not part of this Phase 2 implementation. The `excluded_capabilities` list in LIMITATIONS documents the data-only boundary per provider.
