## Why

`vnstock` now has multiple market-data providers for overlapping capabilities, including KBS, VCI, DNSE, MSN, FMP, and FMarket. Provider redundancy is valuable only if the library can prove that providers remain reachable, compatible, and sufficiently consistent for downstream scanner, backtesting, and AI trading workflows.

Provider APIs may change without notice. Column names, response shapes, price scale, timezone behavior, paging rules, rate limits, or endpoint availability can drift over time. Without provider hardening, the router may fall back from one provider to another while silently changing schema, freshness, or data semantics.

This change introduces provider hardening capabilities: contract samples, live smoke tests, schema drift detection, cross-provider comparison, provider health scoring, and generated capability matrices.

## What Changes

- Add provider contract test structure under `tests/contracts/providers/`.
- Add optional live smoke tests under `tests/live/providers/`.
- Add golden sample fixtures for provider responses and normalized outputs.
- Add cross-provider comparison utilities for overlapping capabilities.
- Add schema drift detection for raw and normalized provider responses.
- Add provider health status and capability metadata.
- Add a generated provider capability matrix from code-level declarations.
- Add clear pass/fail/degraded states for provider readiness.
- Add CI-safe test markers so live network tests are opt-in only.

## Capabilities

### New Capabilities

- `provider-contract-tests`: verify each provider against stored golden response samples and normalized output contracts.
- `provider-live-smoke-tests`: optionally verify that real provider endpoints are reachable and return compatible payloads.
- `cross-provider-comparison`: compare overlapping provider outputs for the same symbol, interval, and date range.
- `schema-drift-detection`: detect raw response and normalized DataFrame schema changes.
- `provider-health-scoring`: produce provider status such as `healthy`, `degraded`, `failing`, or `unknown`.
- `provider-capability-matrix`: generate provider support tables from provider declarations and tests.

### Modified Capabilities

- `provider-router`: may consume provider health state and avoid providers marked as failing or degraded beyond configured thresholds.
- `market-data-fetching`: may expose provider health and comparison metadata for diagnostics.

## Impact

Affected areas:

- `vnstock/core/provider/`
- `vnstock/core/router.py`
- `vnstock/ui/_pools.py`
- `vnstock/explorer/*`
- `tests/contracts/providers/`
- `tests/live/providers/`
- `tests/fixtures/providers/`
- `docs/PROVIDER_HARDENING.md`
- generated docs or artifacts for provider capability matrix

This change does not implement order execution, strategy logic, portfolio management, charting, or notification features.
