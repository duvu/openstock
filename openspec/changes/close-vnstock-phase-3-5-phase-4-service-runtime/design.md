# Design: Close vnstock Phase 3.5 and Phase 4 Service Runtime

## Overview

This change closes the gap between `vnstock` plugin-platform internals and the local data service exposed to `openstock` consumers.

Target flow:

```text
HTTP request
→ canonical endpoint router
→ dataset mapper
→ query parser
→ PluginRuntime.fetch(..., return_result=True)
→ DataResult serializer
→ JSON response envelope
```

No service data endpoint may instantiate legacy `Vnstock` UI objects or provider/explorer classes directly.

## Component design

### 1. Dataset mapper

Add:

```text
vnstock/service/dataset_mapper.py
```

Responsibilities:

- map canonical HTTP paths to dataset names;
- preserve query params such as `source`, `validate`, and `quality_mode`;
- reject unknown datasets clearly;
- optionally support deprecated aliases with a warning.

Canonical mapping:

```text
/v1/equity/ohlcv                 → equity.ohlcv
/v1/equity/quote                 → equity.quote
/v1/equity/intraday-trades       → equity.intraday_trades
/v1/index/ohlcv                  → index.ohlcv
/v1/reference/symbols            → reference.symbols
/v1/company/info                 → reference.company_info
/v1/fundamental/balance-sheet    → fundamental.balance_sheet
/v1/fundamental/income-statement → fundamental.income_statement
/v1/fundamental/cash-flow        → fundamental.cash_flow
/v1/fundamental/financial-ratio  → fundamental.financial_ratio
/v1/fund/nav                     → fund.nav
/v1/fund/holdings                → fund.holdings
```

Temporary aliases may be supported:

```text
/v1/market/ohlcv       → equity.ohlcv
/v1/reference/listing  → reference.symbols
```

### 2. Runtime dependency

Add:

```text
vnstock/service/runtime_dependency.py
```

Responsibilities:

- initialize `default_plugin_registry()`;
- initialize `PluginRuntime`;
- allow test injection of fake runtime;
- avoid expensive per-request setup where practical.

### 3. DataResult serializer

Add:

```text
vnstock/service/serializers.py
```

The serializer converts `DataResult` into:

```json
{
  "data": [],
  "meta": {
    "request_id": "req_...",
    "dataset": "equity.ohlcv",
    "provider": "KBS",
    "quality_status": "PASS",
    "fetched_at": "2026-07-03T00:00:00Z",
    "source_requested": "auto",
    "runtime_path": "plugin_runtime"
  },
  "diagnostics": {
    "routing": {},
    "provider_diagnostics": {},
    "quality": {},
    "warnings": []
  }
}
```

Diagnostics must be redacted and must not expose credential material.

### 4. Provider endpoints

Provider endpoints must use the plugin registry returned by `default_plugin_registry()`.

Expected behavior:

```text
GET /v1/providers              → PluginRegistry.names()
GET /v1/providers/capabilities → PluginRegistry.capability_matrix()
GET /v1/providers/health       → safe health-store summary
```

Do not use the older provider registry for these service endpoints.

### 5. Auth status

Make auth status consistent across CLI and service.

Preferred fix:

```text
AuthManager.auth_status_all(providers: list[str] | None = None)
```

If `providers` is omitted, return status for known auth-capable providers.

### 6. Forbidden boundary

The service must not implement REST login or broker/trading/account/portfolio endpoints. It may return 404 or 405 for unavailable endpoint groups.

### 7. Roadmap alignment

Update `vnstock/roadmap.md` so the REST service target lists only safe auth status/provider endpoints. REST login/logout must be explicitly out of scope.

### 8. Error mapping

Suggested mapping:

```text
unsupported dataset      → 404
no healthy provider      → 503
provider fetch error     → 502
contract validation fail → 422
bad params               → 400
unknown error            → 500
```

Error envelopes should include `error`, `message`, `dataset` when known, and `request_id`.

## Test strategy

Add tests proving:

- `/v1/equity/ohlcv` exists;
- data endpoint calls PluginRuntime;
- response contains `data`, `meta`, and `diagnostics`;
- `meta.runtime_path` is `plugin_runtime`;
- provider endpoints use plugin registry;
- auth status is safe;
- forbidden endpoint groups remain unavailable;
- deprecated aliases, if kept, emit warnings.

## Closure decision

After this change, Phase 3.5 is closed because service data paths no longer bypass PluginRuntime.

Phase 4 is closed because the local data service/auth/Docker boundary is coherent, testable, and aligned with `openstock` service orchestration.
