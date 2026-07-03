# Tasks: Phase 3 — Health-aware Routing and Provider Diagnostics

## 0. Prerequisite check

- [x] Confirm Phase 1 `DatasetContract` exists.
- [x] Confirm Phase 1 `ProviderPlugin` exists.
- [x] Confirm Phase 1 `ProviderRegistry` exists.
- [x] Confirm Phase 1 `ProviderRouter` exists.
- [x] Confirm Phase 1 `DataResult` exists.
- [x] Confirm Phase 2 provider plugins exist.
- [x] Confirm Phase 2 provider capabilities exist.
- [x] Confirm Phase 2 provider limitations metadata exists.

## 1. Provider health model

- [x] Create `vnstock/core/provider/health.py`.
- [x] Add `ProviderHealth`.
- [x] Define health statuses:
  - `HEALTHY`
  - `DEGRADED`
  - `FAILING`
  - `UNKNOWN`
  - `DISABLED`
- [x] Add status semantics docs.
- [x] Add unit tests for health model construction.
- [x] Add unit tests for health status validation.

## 2. Provider health store

- [x] Add `ProviderHealthStore` interface.
- [x] Add `InMemoryProviderHealthStore`.
- [x] Implement `get(provider, dataset)`.
- [x] Implement `set(health)`.
- [x] Implement `record_success(...)`.
- [x] Implement `record_failure(...)`.
- [x] Implement `list_for_dataset(dataset)`.
- [x] Add tests for missing health defaulting to `UNKNOWN`.
- [x] Add tests for success updates.
- [x] Add tests for failure updates.

## 3. Provider cooldown

- [x] Add cooldown model.
- [x] Add cooldown calculation helper.
- [x] Add active cooldown check.
- [x] Add cooldown on repeated failures.
- [x] Add cooldown diagnostics.
- [x] Add tests for short cooldown.
- [x] Add tests for repeated failure cooldown.
- [x] Add tests for cooldown expiry.
- [x] Add tests that active cooldown provider is skipped in auto routing.

## 4. Routing policy

- [x] Add `RoutingPolicy`.
- [x] Add default routing policy.
- [x] Support `prefer_healthy`.
- [x] Support `allow_degraded`.
- [x] Support `allow_failing_fallback`.
- [x] Support `respect_cooldown`.
- [x] Support `use_priority_tiebreaker`.
- [x] Add tests for policy behavior.

## 5. Routing decision and diagnostics

- [x] Add `RoutingDecision`.
- [x] Add routing diagnostics serializer.
- [x] Include dataset.
- [x] Include requested source.
- [x] Include selected provider.
- [x] Include candidate providers.
- [x] Include rejected providers.
- [x] Include fallback flag.
- [x] Include routing reason.
- [x] Include health snapshot.
- [x] Include warnings.
- [x] Add tests for diagnostics completeness.
- [x] Add tests that diagnostics do not contain sensitive credential material.

## 6. ProviderRouter health-aware behavior

- [x] Update `ProviderRouter` to accept health store.
- [x] Update `ProviderRouter` to accept routing policy.
- [x] Implement auto routing by health.
- [x] Implement provider priority tie-breaker.
- [x] Implement active cooldown rejection.
- [x] Implement degraded fallback behavior.
- [x] Ensure failing providers are rejected by default.
- [x] Add option to allow failing fallback through policy.
- [x] Add explicit source behavior with health warning.
- [x] Add tests for healthy provider selection.
- [x] Add tests for degraded fallback.
- [x] Add tests for failing provider rejection.
- [x] Add tests for explicit source degraded warning.
- [x] Add tests for unsupported explicit source.

## 7. Success/failure recording

- [x] Wrap provider fetch with success/failure recording.
- [x] Record latency where available.
- [x] Record freshness score where available.
- [x] Record fetch failure.
- [x] Record validation failure.
- [x] Reset or decay failure count on success.
- [x] Add tests for success after failure.
- [x] Add tests for validation failure marking provider degraded or failing.

## 8. DataResult diagnostics integration

- [x] Attach routing diagnostics to `DataResult.diagnostics`.
- [x] Attach provider diagnostics to `DataResult.diagnostics`.
- [x] Attach selected provider to `DataResult.provider`.
- [x] Preserve existing `DataFrame.attrs`.
- [x] Add tests for DataFrame attrs diagnostics.
- [x] Add tests for backward compatibility of `df.attrs.get("quality")`.

## 9. Provider comparison expansion

- [x] Create or update `vnstock/core/provider/comparison.py`.
- [x] Harden `compare_ohlcv`.
- [x] Add `compare_quote`.
- [x] Add `compare_intraday_shape`.
- [x] Add `compare_coverage`.
- [x] Add `compare_freshness`.
- [x] Add provider-specific tolerance hooks.
- [x] Add tests for OHLCV comparison.
- [x] Add tests for quote comparison.
- [x] Add tests for intraday shape comparison.
- [x] Add tests for freshness comparison.
- [x] Add tests for missing columns before comparison access.

## 10. Error model

- [x] Add `NoProviderForDatasetError`.
- [x] Add `NoHealthyProviderError`.
- [x] Add `ProviderInCooldownError`.
- [x] Add `ProviderDisabledError`.
- [x] Ensure auto routing errors include candidate/rejection context.
- [x] Add tests for error messages.

## 11. Configuration

- [x] Add default provider priority by dataset.
- [x] Use priority as tie-breaker.
- [x] Add tests for priority ordering.
- [x] Document future YAML/env config option.
- [x] Avoid introducing auth policies in Phase 3.

## 12. Documentation

- [x] Add `docs/PROVIDER_ROUTING.md`.
- [x] Add `docs/PROVIDER_DIAGNOSTICS.md`.
- [x] Document health statuses.
- [x] Document routing policy.
- [x] Document explicit source behavior.
- [x] Document auto source behavior.
- [x] Document cooldown behavior.
- [x] Document comparison APIs.
- [x] Document diagnostics examples.
- [x] Document data-only boundary.

## 13. Backward compatibility

- [x] Confirm `Market().equity.ohlcv(...)` remains compatible.
- [x] Confirm explicit `source=` remains compatible.
- [x] Confirm `source="auto"` remains compatible.
- [x] Confirm `validate=True` quality metadata remains compatible.
- [x] Confirm public return type remains `pandas.DataFrame`.

## 14. Validation

Run:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

Phase 3 is complete when:

- [x] provider health model exists;
- [x] provider health store exists;
- [x] cooldown behavior exists;
- [x] routing policy exists;
- [x] routing decision/diagnostics exist;
- [x] router selects providers by health;
- [x] explicit source behavior is preserved;
- [x] diagnostics attach to result metadata;
- [x] comparison APIs are expanded;
- [x] unit tests pass;
- [x] contract tests pass;
- [x] public API remains backward-compatible;
- [x] data-only boundary remains enforced;
- [x] docs are updated.
