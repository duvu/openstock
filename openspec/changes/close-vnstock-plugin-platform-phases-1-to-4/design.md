# Design: Close vnstock Plugin Platform Phases 1 to 4

## Overview

This change is a closure-hardening pass, not a feature-expansion pass.

The goal is to lock the internal plugin architecture so Phase 1, Phase 2, Phase 3, Phase 3.5, and Phase 4 can be marked closed with high confidence.

The closure model is:

```text
architecture exists
→ tests prove behavior
→ docs record scope and boundaries
→ roadmap marks closed phase scope
→ future work is separated cleanly
```

## Phase closure model

### Phase 1: Core contracts and plugin foundation

Phase 1 is closed only if the following are true:

- `ProviderPlugin` is the canonical provider adapter interface.
- `PluginRegistry` manages provider plugin instances.
- `DataResult` is the canonical internal result envelope.
- Dataset contracts exist for the initial dataset set.
- Tests prove registry behavior, result metadata, and contract validation behavior.
- Docs explain the legacy registry vs plugin registry split.

### Phase 2: Provider plugin normalization

Phase 2 is closed only if the following are true:

- all built-in providers register through `default_plugin_registry()`;
- all built-in providers conform to `ProviderPlugin`;
- capability declarations are machine-testable;
- capability matrix is deterministic;
- unsupported datasets are rejected explicitly;
- provider diagnostics are safe to expose.

### Phase 3: Health-aware and auth-aware routing

Phase 3 is closed only if the following are true:

- auto routing selects providers by capability, priority, health, cooldown, and auth policy;
- explicit routing honors explicit provider selection while enforcing hard disabled/cooldown rules;
- routing decisions are serialized into diagnostics;
- provider success and failure update health state;
- auth policy behavior is covered by tests.

### Phase 3.5: PluginRuntime default execution path

Phase 3.5 is closed only if the following are true:

- supported migrated datasets execute through `PluginRuntime`;
- runtime returns `DataResult` when requested;
- default DataFrame output preserves metadata through attrs;
- service data endpoints use `PluginRuntime`;
- tests fail if a migrated path bypasses runtime.

### Phase 4: Auth-aware local data service runtime

Phase 4 is closed only if the following are true:

- local service starts through `vnstock-serve`;
- canonical v1 read-only endpoints route through `PluginRuntime`;
- data responses use `data/meta/diagnostics` envelope;
- provider metadata endpoints use the plugin registry;
- auth status is safe and operational;
- unavailable endpoint groups stay unavailable;
- Docker/local-only deployment remains valid.

## Required implementation areas

### 1. Plugin architecture status document

Add:

```text
vnstock/docs/PLUGIN_ARCHITECTURE_STATUS.md
```

This document should state:

- closed phase scorecard;
- what is closed in Phase 1, 2, 3, 3.5, 4;
- what is not part of these phases;
- external plugin ecosystem as future work;
- data-only boundary;
- runtime-first rule.

### 2. Closure test suite

Add a dedicated closure test suite:

```text
tests/unit/core/test_plugin_architecture_closure.py
tests/unit/service/test_service_runtime_closure.py
tests/contracts/test_builtin_provider_capabilities.py
```

These tests should avoid live provider calls. They should use fake providers, registry inspection, fake runtime injection, and contract fixtures.

### 3. Provider conformance checks

For every provider returned by `default_plugin_registry()`:

- assert it has a valid name;
- assert it conforms to `ProviderPlugin`;
- assert `capabilities()` returns a dict;
- assert every capability has `supported` and `status`;
- assert supported capabilities are only for known dataset names;
- assert unsupported datasets raise the expected unsupported error when fetched directly.

### 4. Contract registry closure

Verify initial dataset contracts include at least:

```text
equity.ohlcv
equity.quote
equity.intraday_trades
index.ohlcv
reference.symbols
reference.company_info
fundamental.balance_sheet
fundamental.income_statement
fundamental.cash_flow
fundamental.financial_ratio
fund.nav
```

If a dataset is intentionally deferred, document it explicitly in `PLUGIN_ARCHITECTURE_STATUS.md`.

### 5. Runtime-first guard

Tests should prove:

- `PluginRuntime.fetch(..., return_result=True)` returns `DataResult`;
- returned DataFrame has runtime metadata in attrs;
- service `/v1/equity/ohlcv` calls injected fake runtime;
- service response includes `meta.runtime_path = plugin_runtime`;
- no supported service data endpoint calls legacy dispatch directly.

### 6. Routing closure

Tests should prove:

- auto routing selects the preferred healthy provider;
- degraded provider is used only as configured fallback;
- failing provider is excluded unless allowed;
- disabled provider is never used;
- cooldown is honored;
- explicit provider selection returns diagnostics;
- auth policy filters providers correctly.

### 7. Service closure

Tests should prove:

- canonical data endpoints exist;
- deprecated aliases still work only if intentionally retained;
- provider endpoints return registry-derived metadata;
- auth status endpoint works with and without auth manager;
- unavailable endpoint groups return not found or method-not-allowed;
- Docker and CLI entrypoints are documented.

### 8. Roadmap alignment

Update `vnstock/roadmap.md` so Phase 1, Phase 2, Phase 3, Phase 3.5, and Phase 4 are shown as closed or closure-ready once this change is implemented.

Move these to future phases:

- external plugin package discovery;
- plugin version negotiation;
- marketplace or third-party provider loading;
- rate limiting;
- batch ingestion;
- storage sinks;
- MCP;
- TUI.

## Target score interpretation

The 97-99 percent target means:

```text
97% = production-shaped internal architecture, fully tested for defined scope
98% = public/service runtime paths are guarded against regression
99% = phase scope documented, no hidden ambiguity, future work separated
```

It does not mean there is no future work. It means the internal plugin-platform phase scope is closed.
