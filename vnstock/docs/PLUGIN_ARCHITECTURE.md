# Plugin Architecture — Phase 1

## Overview

Phase 1 introduces the internal plugin architecture foundation for `vnstock`.

The public API remains **unchanged**. Existing user code continues to work
without modification.

Internally, a plugin-based execution path is now available for provider
adapters that conform to the `ProviderPlugin` protocol.

## Architecture

```text
Market / Reference / Fundamental / Retail UI
        ↓
BaseUI._dispatch()  (existing legacy path — unchanged)
        ↓
ProviderRouter  (new plugin path — resolves by dataset + source)
        ↓
ProviderRegistry  (new plugin registry — holds ProviderPlugin instances)
        ↓
ProviderPlugin  (new protocol — normalized fetch interface)
        ↓
DatasetContract  (canonical dataset shape)
        ↓
QualityValidator  (existing — unchanged)
        ↓
DataResult  (new — wraps DataFrame + metadata)
        ↓
DataFrame return  (public output — unchanged)
```

## New modules (Phase 1)

| Module | Purpose |
|--------|---------|
| `vnstock/core/contracts/` | Dataset contract definitions and registry |
| `vnstock/core/contracts/base.py` | `DatasetContract` model + `DatasetContractRegistry` |
| `vnstock/core/contracts/equity.py` | `equity.ohlcv`, `equity.quote`, `equity.intraday_trades` |
| `vnstock/core/contracts/index.py` | `index.ohlcv` |
| `vnstock/core/contracts/reference.py` | `reference.symbols`, `reference.company_info` |
| `vnstock/core/contracts/fundamental.py` | Balance sheet, income statement, cash flow, ratio |
| `vnstock/core/contracts/fund.py` | `fund.nav` |
| `vnstock/core/contracts/foreign_flow.py` | `foreign_flow.daily` |
| `vnstock/core/provider/plugin.py` | `ProviderPlugin` protocol + `CAPABILITY_STATUSES` |
| `vnstock/core/provider/plugin_registry.py` | `PluginRegistry` — instance-based registry |
| `vnstock/core/provider/plugin_router.py` | `PluginRouter` — dataset → provider resolution |
| `vnstock/core/provider/exceptions.py` | Platform-level exception hierarchy |
| `vnstock/core/result.py` | `DataResult` — structured metadata envelope |

## Existing modules (unchanged)

- `vnstock/core/registry.py` — legacy class-based `ProviderRegistry` (unchanged)
- `vnstock/core/router.py` — UI load-balancer `ProviderRouter` (unchanged)
- `vnstock/ui/` — all public UI modules (unchanged)
- `vnstock/api/` — legacy API adapters (unchanged)
- `vnstock/explorer/` — all provider explorer modules (unchanged)

## Dataset contracts

All 12 built-in contracts are pre-registered in `CONTRACT_REGISTRY`:

```python
from vnstock.core.contracts import CONTRACT_REGISTRY

contract = CONTRACT_REGISTRY.get("equity.ohlcv")
print(contract.required_columns)
# ['symbol', 'time', 'open', 'high', 'low', 'close', 'volume']
```

## Plugin interface

To conform to `ProviderPlugin`, a class must expose:

```python
class MyProvider:
    name: str  # e.g. "MY_PROVIDER"

    def capabilities(self) -> dict: ...
    def fetch(self, dataset: str, params: dict) -> pd.DataFrame: ...
    def validate_params(self, dataset: str, params: dict) -> None: ...
    def diagnostics(self) -> dict: ...
```

See `vnstock/core/provider/plugin.py` for the full protocol definition.

## DataResult

Internal pipeline results should use `DataResult`:

```python
from vnstock.core.result import DataResult
from datetime import datetime

result = DataResult(
    dataset="equity.ohlcv",
    provider="KBS",
    data=df,
    quality_status="PASS",
    quality_report=quality_dict,
    diagnostics=routing_diag,
    fetched_at=datetime.utcnow(),
)

df_out = result.to_dataframe()
# df_out.attrs["provider"] == "KBS"
# df_out.attrs["quality"] == quality_dict  (backward compat key)
# df_out.attrs["quality_status"] == "PASS"
```

`DataResult` must not contain any auth secrets. See
`vnstock/core/result.py` for the list of forbidden metadata keys.

## What is NOT in Phase 1

- External provider packages (`vnstock-provider-*`)
- Python entry point discovery
- Health-aware or auth-aware routing
- CLI/TUI/API service
- Storage sinks or batch ingestion
- Recommendation engine or trading signals

These are planned for future phases.
