# Tasks: FiinQuantX Provider Integration

## 0. Governance and commercial boundary

- [ ] 0.1 Confirm the commercial agreement permits the intended local SDK use, normalized persistence, derived analytics, caching, and local service exposure. [evidence: reviewed license decision record]
- [ ] 0.2 Document prohibited redistribution, raw archive, bulk export, multi-user exposure, and fixture behavior. [evidence: `docs/providers/FIINQUANTX.md`]
- [ ] 0.3 Preserve the **read-only research boundary**; do not expose broker, account, portfolio, order, allocation, margin, transfer, execution, or automated-trading APIs even if the SDK contains them. [evidence: provider capability and service-boundary tests]
- [ ] 0.4 Do not commit or redistribute the FiinQuantX wheel, proprietary SDK source, licensed documentation, credentials, or raw licensed production payloads. [evidence: repository hygiene and fixture review]
- [ ] 0.5 Register FiinQuantX as an optional provider; base `vnstock` installation and imports must remain functional without it. [evidence: clean-environment import tests]

## 1. FQ-0 licensed SDK contract discovery

- [ ] 1.1 Install one approved FiinQuantX SDK version from the official distribution in an isolated licensed environment. [evidence: redacted environment record]
- [ ] 1.2 Record the tested wheel version, supported Python version, package/import names, and installation mechanism. [evidence: contract inventory]
- [ ] 1.3 Inventory public SDK classes, functions, call signatures, return types, and documented exceptions without capturing secrets or proprietary source. [evidence: redacted contract inventory]
- [ ] 1.4 Determine authentication/session lifecycle, credential inputs, refresh behavior, and logout/cleanup semantics. [evidence: auth decision record]
- [ ] 1.5 Determine entitlement and subscription-status APIs or safe failure signals. [evidence: entitlement matrix]
- [ ] 1.6 Determine rate, connection, request, and quota limits visible through the plan/SDK. [evidence: quota policy record]
- [ ] 1.7 Verify dataset methods, parameters, intervals, pagination, units, timestamps, time zones, revision semantics, and raw field shapes for the approved MVP matrix. [evidence: dataset contract inventory]
- [ ] 1.8 Determine whether financial records include publication/availability timestamps, consolidation scope, audit status, and restatement identity. [evidence: fundamentals availability matrix]
- [ ] 1.9 Produce synthetic fixtures that reproduce verified response shapes without licensed values. [evidence: fixture provenance review]
- [ ] 1.10 Keep every unverified dataset marked `discovery_pending` or unsupported. [evidence: capability matrix test]

## 2. FQ-1 provider foundation

- [ ] 2.1 Add `vnstock/providers/fiinquantx/` package with lazy SDK bridge, plugin, auth, entitlement, diagnostics, exceptions, capabilities, mappings, and normalization modules. [depends: 1.1–1.10]
- [ ] 2.2 Implement lazy import and distinguish not-installed, incompatible-version, unauthenticated, not-entitled, quota-exhausted, and provider-failure states. [evidence: unit tests]
- [ ] 2.3 Pin and expose the initially supported SDK version/compatibility policy. [evidence: version tests and diagnostics]
- [ ] 2.4 Implement `FiinQuantXProviderPlugin` conforming to `ProviderPlugin`. [evidence: provider conformance tests]
- [ ] 2.5 Register the provider in the built-in plugin registry without breaking registry creation when the SDK is absent. [evidence: registry tests]
- [ ] 2.6 Route all service data fetches through `PluginRuntime`; add a regression test preventing direct provider bypass. [evidence: service-runtime tests]
- [ ] 2.7 Map the verified authentication model into existing `AuthSpec`, credential stores, and safe auth status. [evidence: auth tests]
- [ ] 2.8 Redact usernames, passwords, tokens, cookies, keys, customer IDs, and raw auth responses from logs, exceptions, diagnostics, attrs, REST, TUI, notebooks, and MCP surfaces. [evidence: secret/redaction tests]
- [ ] 2.9 Implement entitlement-aware capability filtering before provider I/O. [evidence: entitlement tests]
- [ ] 2.10 Implement typed provider exceptions and wrap them into existing platform errors at the plugin boundary. [evidence: error-contract tests]
- [ ] 2.11 Add safe diagnostics for SDK version, installation, auth state, subscription state, entitlement, quota aggregates, latency, health, and cooldown. [evidence: diagnostics tests]

## 3. FQ-1 rate and quota controls

- [ ] 3.1 Add provider-scoped rate limiting using verified FiinQuantX limits. [depends: 1.6]
- [ ] 3.2 Add connection/session concurrency controls. [evidence: concurrency tests]
- [ ] 3.3 Add bounded retry with jitter only for verified retryable failures. [evidence: retry tests]
- [ ] 3.4 Do not retry auth, entitlement, invalid-input, incompatible-version, or hard quota failures. [evidence: negative tests]
- [ ] 3.5 Record success/failure into provider health and cooldown state. [evidence: routing health tests]
- [ ] 3.6 Add quota preflight for bounded batch operations and return structured partial results rather than unbounded retries. [evidence: batch/quota tests]
- [ ] 3.7 Ensure `source="auto"` considers quota budget and configurable commercial-provider priority. [evidence: routing-decision tests]

## 4. FQ-2 reference and EOD market datasets

- [ ] 4.1 Implement verified `reference.symbols` mapping and symbol normalization. [depends: 2.1–2.11]
- [ ] 4.2 Implement verified `equity.ohlcv` mapping, including interval/date validation, price scale, volume/value units, and adjustment state. [evidence: contract tests]
- [ ] 4.3 Implement verified `index.ohlcv` mapping. [evidence: contract tests]
- [ ] 4.4 Implement `equity.quote` only if the SDK contract is verified and entitlement permits it. [evidence: contract tests or explicit unsupported evidence]
- [ ] 4.5 Preserve `provider=FIINQUANTX`, SDK version, fetch timestamp, provider method/dataset identity, request window, quality, routing, and safe entitlement lineage. [evidence: `DataResult` tests]
- [ ] 4.6 Add synthetic fixtures for valid, empty, invalid-symbol, unsupported-interval, missing-field, and schema-drift responses. [evidence: fixture tests]
- [ ] 4.7 Add cross-provider OHLCV comparison against approved KBS/VCI fixtures and typed divergence diagnostics. [evidence: comparison tests]
- [ ] 4.8 Preserve existing public UI and explicit-source behavior for all current providers. [evidence: backward-compatibility suite]

## 5. FQ-3 market structure, foreign flow, and valuation

- [ ] 5.1 Implement `foreign_flow.daily` using verified buy/sell volume/value, net-flow, ownership-room, date, symbol, and lineage semantics. [evidence: contract tests]
- [ ] 5.2 Add `reference.index_constituents` contract and adapter if verified. [evidence: contract/registry tests]
- [ ] 5.3 Add `reference.free_float_history` contract and adapter if verified. [evidence: contract/registry tests]
- [ ] 5.4 Add `reference.share_outstanding` contract and adapter if verified. [evidence: contract/registry tests]
- [ ] 5.5 Add `reference.foreign_ownership_limit` contract and adapter if verified. [evidence: contract/registry tests]
- [ ] 5.6 Add `market.market_cap_history` contract and adapter if verified. [evidence: contract/registry tests]
- [ ] 5.7 Add `market.breadth` contract and adapter if verified. [evidence: contract/registry tests]
- [ ] 5.8 Add `valuation.history` contract and adapter if verified, preserving metric code, value, date/period, entity scope, and methodology/source metadata. [evidence: contract tests]
- [ ] 5.9 Define uniqueness, revision, freshness, and unit policy for every new contract. [evidence: contract registry tests]
- [ ] 5.10 Add capability matrix, REST service, and documentation entries only for implemented and entitled datasets. [evidence: service/capability tests]

## 6. FQ-4 publication-aware fundamentals

- [ ] 6.1 Implement verified `fundamental.balance_sheet` mapping. [depends: 1.8]
- [ ] 6.2 Implement verified `fundamental.income_statement` mapping.
- [ ] 6.3 Implement verified `fundamental.cash_flow` mapping.
- [ ] 6.4 Implement verified `fundamental.financial_ratio` mapping.
- [ ] 6.5 Preserve fiscal period end, period type, publication/available-from time, consolidation scope, audit/review state, currency, unit, provider record identity, and restatement/version identity where supplied. [evidence: normalization tests]
- [ ] 6.6 Mark records without defensible publication time as unsuitable for historical as-of analysis rather than fabricating availability. [evidence: no-lookahead tests]
- [ ] 6.7 Preserve original and restated records separately when source version identity is available. [evidence: restatement tests]
- [ ] 6.8 Test annual/quarterly, bank/non-bank, consolidated/separate, audited/reviewed/unaudited, missing-period, and restatement cases. [evidence: focused suite]
- [ ] 6.9 Document mapping limitations and fields that remain provider-specific. [evidence: provider documentation]

## 7. FQ-5 optional intraday and vendor-derived datasets

- [ ] 7.1 Add intraday OHLCV only after timestamp, session, sequence, entitlement, and retention semantics are verified.
- [ ] 7.2 Add `equity.order_book_snapshot` only after snapshot/depth/sequence semantics are verified.
- [ ] 7.3 Add `equity.aggressor_flow` only after buy/sell classification semantics are verified.
- [ ] 7.4 Add `foreign_flow.intraday` only after session completeness and revision semantics are verified.
- [ ] 7.5 Add `indicator.vendor_derived` for vendor-calculated indicators without silently replacing deterministic OpenStock formulas.
- [ ] 7.6 Apply conservative cache and storage retention policies for high-frequency licensed data. [evidence: policy tests]

## 8. Service, CLI, and diagnostics

- [ ] 8.1 Expose FiinQuantX through existing canonical SDK/UI and local REST data endpoints only; do not create provider-specific data endpoints unless required for safe metadata. [evidence: API tests]
- [ ] 8.2 Add safe provider installation/auth/entitlement/health status to provider metadata endpoints. [evidence: API tests]
- [ ] 8.3 Do not add REST login/logout or raw-secret inputs. [evidence: forbidden-route tests]
- [ ] 8.4 Add explicit-source examples and diagnostics to provider documentation.
- [ ] 8.5 Add a bounded example script that uses a licensed local environment and never prints credentials or raw auth payloads.
- [ ] 8.6 Update capability matrix and provider hardening docs.

## 9. Testing and validation

- [ ] 9.1 Add offline synthetic provider conformance tests.
- [ ] 9.2 Add dataset contract tests for every enabled capability.
- [ ] 9.3 Add auth, entitlement, quota, version, schema-drift, error-redaction, and runtime-path tests.
- [ ] 9.4 Add opt-in live smoke tests guarded by `VNSTOCK_LIVE_TESTS`, `VNSTOCK_LIVE_PROVIDERS=FIINQUANTX`, and a licensed-environment acknowledgement.
- [ ] 9.5 Ensure live tests use minimal bounded requests and do not emit raw licensed payloads.
- [ ] 9.6 Run targeted FiinQuantX tests.
- [ ] 9.7 Run all provider, contract, auth, runtime, service, and quality tests.
- [ ] 9.8 Run Ruff check and format check for `vnstock`.
- [ ] 9.9 Run package build without FiinQuantX installed.
- [ ] 9.10 Run package/runtime checks with the approved FiinQuantX version installed.
- [ ] 9.11 Run strict OpenSpec validation.
- [ ] 9.12 Record exact commit, commands, outcomes, SDK version, Python version, and licensed test scope in `validation.md`.

## Phase gates

- [ ] G0 Licensed contract, entitlement, schema, and license discovery is complete; no method or dataset remains guessed in an enabled capability.
- [ ] G1 Optional provider foundation, auth, entitlement, diagnostics, runtime routing, and redaction pass without breaking base installation.
- [ ] G2 Reference and EOD market datasets pass canonical contract and cross-provider comparison tests.
- [ ] G3 Foreign flow, index structure, breadth, market-cap, and valuation contracts pass where licensed and verified.
- [ ] G4 Publication-aware fundamentals pass historical no-lookahead and restatement tests.
- [ ] G5 Optional intraday/vendor-derived capabilities pass their independent retention and session contracts.
- [ ] G6 Full `vnstock` regression, packaging, live-smoke, and strict OpenSpec evidence is attached to the exact implementation commit.