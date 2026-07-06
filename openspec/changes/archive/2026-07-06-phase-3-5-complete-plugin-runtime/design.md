# Design: Phase 3.5 — Complete Plugin Runtime and Retire Legacy Dispatch

## Overview

This phase introduces `PluginRuntime`, a single execution facade for all public data requests.

Current architecture has both:

```text
Legacy public API → explorer/provider classes directly
```

and:

```text
PluginRegistry → PluginRouter → ProviderPlugin
```

This phase makes the second path the default and retires the first as a public dispatch mechanism.

## Target architecture

```text
Market / Reference / Fundamental / Retail
        ↓
DatasetRequest
        ↓
PluginRuntime
        ↓
DatasetContractRegistry
        ↓
PluginRegistry
        ↓
PluginRouter
        ↓
ProviderPlugin
        ↓
Provider fetch / normalize
        ↓
DataResult
        ↓
DataFrame
```

## Key distinction

This phase does not require deleting all old provider client code immediately.

Allowed:

```text
ProviderPlugin
→ uses old explorer/client class internally
→ normalizes output
→ returns contract-compliant DataFrame
```

Forbidden:

```text
Public API
→ directly calls old explorer/client class
→ bypasses PluginRouter
→ bypasses DataResult
→ bypasses diagnostics
```

## PluginRuntime

Suggested module:

```text
vnstock/core/runtime/plugin_runtime.py
```

Suggested responsibilities:

```text
1. Accept dataset name and request params.
2. Resolve dataset contract.
3. Resolve provider using PluginRouter.
4. Call provider.validate_params().
5. Call provider.fetch().
6. Optionally validate result against DatasetContract.
7. Record provider success/failure.
8. Wrap result in DataResult.
9. Attach routing/provider diagnostics.
10. Return DataFrame for public compatibility.
```

Suggested conceptual API:

```python
class PluginRuntime:
    def fetch(
        self,
        dataset: str,
        params: dict,
        source: str | None = None,
        validate: bool = False,
        return_result: bool = False,
    ) -> pd.DataFrame | DataResult:
        ...
```

## DatasetRequest

Add a small request model to prevent ad-hoc parameter passing.

Suggested fields:

```text
dataset
params
source
validate
quality_mode
return_result
```

This does not need to be a heavy abstraction. A dataclass is enough.

## Public API integration

Public UI classes should map current methods to canonical datasets.

Examples:

```text
Market().equity.ohlcv(...)
→ dataset = equity.ohlcv

Market().equity.quote(...)
→ dataset = equity.quote

Market().equity.intraday(...)
→ dataset = equity.intraday_trades

Reference().symbols(...)
→ dataset = reference.symbols

Reference().company_info(...)
→ dataset = reference.company_info

Fundamental().balance_sheet(...)
→ dataset = fundamental.balance_sheet

Retail().fund.nav(...)
→ dataset = fund.nav
```

## Compatibility policy

The public return type remains `pandas.DataFrame`.

`DataResult` is internal by default.

Advanced callers may request:

```text
return_result=True
```

to receive full `DataResult`.

## Legacy fallback policy

Temporary fallback is allowed only when:

- no provider plugin supports the dataset yet;
- the dataset is documented as not migrated;
- fallback emits diagnostics;
- tests mark the fallback as transitional.

Fallback must not silently bypass plugin runtime for migrated datasets.

Suggested fallback diagnostic:

```python
{
    "runtime": "legacy_fallback",
    "dataset": "unknown.dataset",
    "reason": "dataset not yet migrated to plugin runtime",
}
```

## Provider plugin registration

Add a central provider bootstrap function.

Suggested module:

```text
vnstock/core/runtime/bootstrap.py
```

Suggested API:

```python
def default_plugin_registry() -> PluginRegistry:
    ...
```

The bootstrap should register:

```text
KBS
VCI
DNSE
TCBS
FMarket
MSN
FMP
```

## DataResult integration

Every plugin runtime fetch should produce `DataResult`.

Required diagnostics:

```text
dataset
provider
routing decision
provider diagnostics
quality status
fallback status
runtime path
```

For public DataFrame return:

```text
df.attrs["dataset"]
df.attrs["provider"]
df.attrs["quality_status"]
df.attrs["quality"]
df.attrs["diagnostics"]
df.attrs["fetched_at"]
```

## Health update integration

PluginRuntime should call:

```text
router.record_success(...)
router.record_failure(...)
```

or equivalent health store methods after provider fetch/validation.

## Migration stages

### Stage 1 — Runtime added but not default

Add `PluginRuntime` and tests.

### Stage 2 — Runtime enabled behind flag

Add temporary config:

```text
VNSTOCK_USE_PLUGIN_RUNTIME=1
```

### Stage 3 — Runtime default

Make plugin runtime the default for migrated datasets.

### Stage 4 — Remove silent legacy dispatch

For migrated datasets, direct legacy dispatch must be removed.

### Stage 5 — Delete or quarantine legacy public dispatch

Old public dispatch utilities should be deleted, renamed internal, or marked private.

## Data-only boundary

This phase keeps the existing data-only boundary.

Plugin runtime must not expose:

- trading signals;
- stock recommendations;
- broker execution;
- order placement;
- account APIs;
- portfolio APIs;
- trading bots.

## Risks

### Risk 1: Breaking public API behavior

Mitigation:

- preserve method signatures;
- preserve DataFrame return type;
- add snapshot/compatibility tests.

### Risk 2: Provider plugin output differs from legacy output

Mitigation:

- compare plugin output against legacy output before retiring path;
- document acceptable schema normalization differences.

### Risk 3: Hidden legacy fallback remains

Mitigation:

- add tests that assert migrated datasets do not call fallback;
- add runtime diagnostics;
- add deprecation warnings for fallback use.

### Risk 4: Phase 4 service bypasses runtime

Mitigation:

- define Phase 4 service endpoints as wrappers around `PluginRuntime.fetch()` only.

## Open questions

1. Should plugin runtime be default immediately or behind env flag for one release?
2. Should `return_result=True` be public?
3. Should legacy explorer classes remain importable?
4. Should migrated datasets fail if plugin route fails, or fallback to legacy for one release?
5. Should fallback be controlled by `allow_legacy_fallback=False` default?
