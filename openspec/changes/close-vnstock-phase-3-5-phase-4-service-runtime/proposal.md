# Change Proposal: Close vnstock Phase 3.5 and Phase 4 Service Runtime

## Change ID

`close-vnstock-phase-3-5-phase-4-service-runtime`

## Summary

Move the remaining Phase 3.5 and Phase 4 closure requirements into the `openstock` orchestration repository.

`vnstock` already has PluginRuntime, provider plugin bootstrap, auth core, CLI auth, CLI serve, local HTTP service, Docker packaging, and service boundary tests. The remaining issue is alignment: service data endpoints still bypass PluginRuntime and use legacy dispatch for data fetches.

This change closes Phase 3.5 and Phase 4 by requiring the `vnstock-service` HTTP layer to route supported data endpoints through PluginRuntime, serialize DataResult into a stable service envelope, expose canonical data API paths, and keep the auth/trading boundary closed.

## Problems to fix

1. Data endpoints currently use legacy dispatch instead of PluginRuntime.
2. Current endpoint shape uses `/v1/market/...`; the target service contract uses canonical paths such as `/v1/equity/ohlcv`.
3. Data responses lack a stable `meta` and `diagnostics` envelope.
4. Provider metadata endpoints must use the plugin registry, not the older provider registry.
5. Auth status call sites must be made consistent and safe.
6. Roadmap/API docs must not approve REST login or trading/account endpoints.

## Goals

### G1. Route service data through PluginRuntime

All supported data endpoints MUST call `PluginRuntime.fetch(..., return_result=True)`.

### G2. Add canonical v1 read-only data endpoints

Required canonical endpoints:

```text
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/equity/intraday-trades
GET /v1/index/ohlcv
GET /v1/reference/symbols
GET /v1/company/info
GET /v1/fundamental/balance-sheet
GET /v1/fundamental/income-statement
GET /v1/fundamental/cash-flow
GET /v1/fundamental/financial-ratio
GET /v1/fund/nav
GET /v1/fund/holdings
```

### G3. Return a stable DataResult envelope

All successful data endpoints MUST return:

```text
data
meta
diagnostics
```

### G4. Use plugin registry for provider endpoints

Provider and capability endpoints MUST use the default plugin registry/bootstrap.

### G5. Preserve local command-based auth

The service MAY expose safe auth status, but MUST NOT expose REST login.

### G6. Preserve data-only boundary

The service MUST NOT expose account, order, portfolio, transfer, margin, or trading execution APIs.

## Non-goals

This change does not implement rate limiting, retry, batch ingestion, archive/storage sinks, MCP, TUI, new providers, stock recommendation, broker execution, or pattern detection.

## Success criteria

Phase 3.5 is closed when service data endpoints use PluginRuntime and tests fail if runtime is bypassed.

Phase 4 is closed when `vnstock-serve` starts a local data-read service, canonical v1 endpoints return envelopes, provider endpoints return plugin metadata, auth status is safe, forbidden endpoint groups remain unavailable, and Docker/local-only deployment works.

## Validation commands

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core/runtime tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```
