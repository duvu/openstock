# Tasks: FiinQuantX Data Provider Integration

## 0. Governance, licensing and product boundary

- [ ] 0.1 Confirm the commercial agreement permits local SDK use, normalized caching/persistence, derived research analytics and the intended local service exposure. [evidence: reviewed license decision matrix]
- [x] 0.2 Record decisions for in-memory cache, SQLite cache, normalized files, DuckDB/Postgres sinks, raw archive, local REST, multi-user/public exposure, bulk export, model training and derived analytics. [evidence: `vnstock/docs/providers/FIINQUANTX.md`]
- [ ] 0.3 Preserve the **read-only research boundary**. Exclude broker login, account, loan/funding, cash/buying power, order, position, portfolio, transfer, margin and execution SDK surfaces. [evidence: positive-allowlist and forbidden-member architecture tests]
- [x] 0.4 Do not vendor or redistribute the FiinQuantX wheel, proprietary source, credentials, session data or licensed production rows. [evidence: dependency, repository-hygiene and fixture review]
- [x] 0.5 Define a secure exact-version installation procedure for the official package index; do not rely on an unpinned mixed-index install. [evidence: installation decision record]
- [x] 0.6 Keep base `vnstock` installation, import, registry construction, tests and package build functional without FiinQuantX installed. [evidence: clean base-image import and offline registry tests at `0bd6a5d`]

## 1. FQ-0A documentation contract inventory

- [x] 1.1 Review the official `fiinquant/fiinquantx` package repository at commit `abb1e038f3e7401ab770067c5d7a539a06823097`. [evidence: `source-review.md`]
- [x] 1.2 Record the latest indexed wheel at review time as `fiinquantx-0.1.64-py3-none-any.whl`. [evidence: `source-review.md`]
- [x] 1.3 Review the detailed FiinQuant documentation mirror committed by `30b684d48911a3e0cf6e7c98fac6a2aa2b790f24` and merged through PR #103. [evidence: `source-review.md`]
- [x] 1.4 Record documented installation and `FiinSession(username, password).login()` authentication syntax. [evidence: `source-review.md`]
- [x] 1.5 Inventory documented synchronous methods: `TickerList`, `BasicInfor`, historical `Fetch_Trading_Data`, `PriceStatistics`, `MarketDepth`, `MarketBreadth`, `FundamentalAnalysis`, `StockScreening` and `MoneyFlow.get_contribution`. [evidence: `source-review.md`]
- [x] 1.6 Inventory documented streaming methods: `Trading_Data_Stream`, realtime `Fetch_Trading_Data` and `BidAsk`. [evidence: `source-review.md`]
- [x] 1.7 Identify documentation inconsistencies for SDK version, return type, timestamp type, field casing, `fb/fs` direction, free-float unit and fundamentals publication time. [evidence: `source-review.md`]
- [x] 1.8 Identify and exclude all documented section-7 trading/account/position/order capabilities. [evidence: `source-review.md`, `proposal.md`, normative spec]

## 2. FQ-0B licensed runtime and commercial contract verification

- [ ] 2.1 Install one approved exact FiinQuantX version in an isolated licensed environment using the reviewed secure installation procedure. [depends: 0.5] [evidence: exact runtime install recorded at `0bd6a5d`; commercial approval remains pending]
- [x] 2.2 Record installed package metadata, import name, supported Python versions and operating systems. [evidence: runtime contract inventory at `0bd6a5d`]
- [x] 2.3 Probe the documented positive allowlist and confirm actual classes, methods, call signatures and return object types without extracting proprietary implementation source. [evidence: redacted API probe at `0bd6a5d`]
- [ ] 2.4 Verify login success/failure, session reuse, expiry, concurrent-session behavior and safe cleanup. [evidence: auth probe]
- [ ] 2.5 Verify exception types and distinguish credentials, authentication, access/entitlement, rate limit, quota, invalid request, valid empty and provider failure. [evidence: failure matrix]
- [ ] 2.6 Determine account/package entitlement differences, especially financial-ratio fields and market-data depth. [evidence: entitlement matrix]
- [ ] 2.7 Determine requests-per-second/minute/month, connection limits, batch limits and observable quota signals, or record conservative configured limits if no API exists. [evidence: limit policy]
- [ ] 2.8 Verify historical `Fetch_Trading_Data` return type, columns, dtypes, timestamp/timezone, supported asset types, interval aliases, `adjusted`, `lasted`, period/from-date exclusivity and empty behavior. [evidence: market-data probe]
- [ ] 2.9 Verify `bu`, `sd`, `fb`, `fs`, `fn` units, sign and buy/sell direction. [evidence: flow-field probe]
- [ ] 2.10 Verify `PriceStatistics` return types and schemas for overview, foreign, free float, ceiling/floor and investor flow. [evidence: statistics probe]
- [ ] 2.11 Resolve `freefloat` unit and scale. Keep capability disabled if unresolved. [evidence: free-float decision]
- [ ] 2.12 Verify `TickerList` current-membership semantics and `BasicInfor` reference shape. [evidence: reference probe]
- [ ] 2.13 Verify stock/sector/index valuation methods, entity identifiers, date fields and P/E/P/B units. [evidence: valuation probe]
- [ ] 2.14 Verify `MarketBreadth.get()` freshness and whether it is current-only. [evidence: breadth probe]
- [ ] 2.15 Verify nested statement/ratio shapes across manufacturing, securities, banking and insurance; annual/quarterly; consolidated/separate; audited/unaudited. [evidence: fundamental shape matrix]
- [ ] 2.16 Verify whether any fundamental response supplies publication/available-from time, currency/unit or restatement identity. [evidence: temporal/version matrix]
- [ ] 2.17 Produce manually reviewed synthetic fixtures for every enabled synchronous capability; fixtures contain no licensed values. [evidence: fixture provenance]
- [x] 2.18 Leave undocumented or unresolved capabilities disabled. [evidence: capability matrix and live service probe at `0bd6a5d`]

## 3. FQ-1 optional provider foundation

- [ ] 3.1 Add `vnstock/vnstock/providers/fiinquantx/` with plugin, lazy SDK bridge, session adapter, capabilities, method allowlist, version policy, limits, mappings, normalizers, diagnostics and typed exceptions. [depends: 2.1–2.18] [evidence: bounded implementation exists at `0bd6a5d`; prerequisite verification remains incomplete]
- [ ] 3.2 Implement lazy SDK import and safe states for absent package, untested version, missing credentials, auth failure and authenticated session. [evidence: unit tests]
- [x] 3.3 Implement exact-version contract compatibility and expose safe SDK/contract version diagnostics. [evidence: bridge and diagnostics tests at `0bd6a5d`]
- [x] 3.4 Implement the positive SDK method allowlist and forbidden trading/account member set. [evidence: architecture tests]
- [x] 3.5 Implement `FiinQuantXProviderPlugin` conforming to `ProviderPlugin`. [evidence: protocol/conformance tests]
- [x] 3.6 Register the provider in `default_plugin_registry()` without requiring the SDK at registry-construction time. [evidence: registry tests]
- [ ] 3.7 Route all public/service synchronous FiinQuantX fetches through `PluginRuntime`; prevent direct SDK bypass. [evidence: service runtime tests and HTTP smoke at `0bd6a5d`; complete bypass audit remains pending]
- [x] 3.8 Resolve credentials only from approved local credential sources and create sessions lazily. [evidence: session boundary tests at `0bd6a5d`]
- [ ] 3.9 Redact credentials, session state, tokens/cookies, account IDs and raw auth responses from logs, exceptions, diagnostics, attrs and service responses. [evidence: secret/redaction tests]
- [ ] 3.10 Implement static implemented-capability declarations plus short-lived runtime access/entitlement observations. [evidence: capability/access tests]
- [x] 3.11 Implement typed provider errors and platform exception wrapping. [evidence: provider and service error tests at `0bd6a5d`]
- [ ] 3.12 Implement safe diagnostics for installation, SDK version, contract version, credential configuration, auth state, implemented datasets, observed access, limit policy, latency, health and cooldown. [evidence: diagnostics tests]

## 4. FQ-1 provider limits and routing

- [ ] 4.1 Implement provider-local request/concurrency limits using verified or conservatively configured values. [depends: 2.7]
- [ ] 4.2 Validate symbols, dates, intervals, period/start exclusivity and bounded request windows before session creation/provider I/O. [evidence: fail-before-I/O tests]
- [ ] 4.3 Retry only verified transient failures with bounded attempts/backoff/jitter. [evidence: retry tests]
- [ ] 4.4 Do not retry invalid input, credentials/auth, access, unsupported dataset, untested version, schema failure or hard quota failure. [evidence: negative tests]
- [ ] 4.5 Record success/failure into existing provider health/cooldown state. [evidence: router-health tests]
- [x] 4.6 Preserve explicit `source=FIINQUANTX` no-fallback semantics. [evidence: unsupported explicit-source service test at `0bd6a5d`]
- [ ] 4.7 Let `source=auto` consider capability, auth/access, health/cooldown, commercial priority, freshness, adjustment requirement, quota budget and deployment policy. [evidence: routing-decision tests]

## 5. FQ-2 reference and historical market data

- [ ] 5.1 Implement `equity.ohlcv` through `Fetch_Trading_Data(realtime=False)` with verified interval, date, adjusted-price, incomplete-bar, timestamp, price-scale, volume and value semantics. [evidence: contract tests]
- [ ] 5.2 Implement `index.ohlcv` through the same allowlisted method with index-entity validation. [evidence: contract tests]
- [ ] 5.3 Keep `bu`, `sd`, `fb`, `fs` and `fn` outside canonical OHLCV; map them only through approved flow contracts. [evidence: schema tests]
- [ ] 5.4 Implement `reference.company_info` through `BasicInfor(...).get()` with company, exchange, tax-code and ICB hierarchy mappings. [evidence: contract tests]
- [x] 5.5 Add and implement `reference.index_membership_snapshot` through `TickerList(index)`. Preserve observation time and do not claim historical effective dates. [evidence: contract tests and live service smoke at `0bd6a5d`]
- [x] 5.6 Add and implement `reference.sector_membership_snapshot` through `TickerList(sector_alias_or_icb_code)`. [evidence: contract tests and live service smoke at `0bd6a5d`]
- [ ] 5.7 Enable `reference.symbols` only if a complete current universe and security classification are verified; do not synthesize it from a few index lists. [evidence: complete-universe probe or explicit unsupported status]
- [ ] 5.8 Add and implement `market.price_limits.daily` through `get_ceilingfloor()` after price-scale verification. [evidence: contract tests]
- [ ] 5.9 Do not advertise synchronous `equity.quote` from realtime streaming documentation. [evidence: capability test]
- [ ] 5.10 Add versioned synthetic fixtures for valid, empty, invalid, missing-field, timestamp-variant and field-casing cases. [evidence: fixture tests]
- [ ] 5.11 Compare bounded adjusted and unadjusted OHLCV against approved KBS/VCI fixtures; emit typed divergence diagnostics. [evidence: comparison tests]
- [ ] 5.12 Preserve existing public calls and current provider behavior when FiinQuantX is unavailable. [evidence: backward-compatibility suite]

## 6. FQ-3 flow, ownership, market structure and valuation

- [ ] 6.1 Implement `foreign_flow.daily` from verified `get_foreign()` matched/deal/total buy/sell/net value and volume fields. [evidence: contract tests]
- [ ] 6.2 Add and implement `foreign_ownership.daily` for current/total room, room percentage, owned shares/value semantics and ownership percentage. [evidence: contract tests]
- [ ] 6.3 Add and implement dimensioned `investor_flow.daily` from `get_value_by_investor()` for domestic individual, domestic institutional, foreign individual, foreign institutional and proprietary flow. [evidence: contract tests]
- [ ] 6.4 Keep derivatives `openInterest` outside equity investor-flow rows; add it only through an approved derivative contract. [evidence: asset-boundary tests]
- [ ] 6.5 Add and implement `market.market_cap_history` from `get_overview()`, preserving Daily/Weekly/Monthly/Quarterly/Yearly aggregation semantics. [evidence: contract tests]
- [ ] 6.6 Add and implement `reference.free_float_history` only after unit/scale verification. [evidence: contract tests or disabled capability evidence]
- [ ] 6.7 Add and implement current `market.breadth_snapshot` from `MarketBreadth.get()`; do not claim historical breadth. [evidence: contract tests]
- [ ] 6.8 Add and implement separate `valuation.stock.daily`, `valuation.sector.daily` and `valuation.index.daily` contracts. [evidence: contract tests]
- [ ] 6.9 Preserve ICB level for sector valuation and entity type for every valuation row. [evidence: schema tests]
- [ ] 6.10 Keep direct outstanding-share history unsupported unless a verified SDK field/method is found. [evidence: capability test]
- [ ] 6.11 Define uniqueness, units, sign, freshness, frequency and revision policy for each new contract. [evidence: contract registry tests]
- [ ] 6.12 Add capability matrix and local service exposure only for enabled contracts and permitted license behavior. [evidence: service/capability tests]

## 7. FQ-4 period-aware structured fundamentals

- [ ] 7.1 Implement company-type-aware nested mapping for `fundamental.balance_sheet`. [depends: 2.15]
- [ ] 7.2 Implement `fundamental.income_statement`.
- [ ] 7.3 Implement `fundamental.cash_flow`.
- [ ] 7.4 Implement `fundamental.financial_ratio`, preserving vendor ratio group/code and subscription-dependent availability. [evidence: contract tests]
- [ ] 7.5 Preserve fiscal year, quarter/annual period, statement type, consolidated/separate scope, audited flag, company type and vendor field path. [evidence: normalization tests]
- [ ] 7.6 Verify and preserve currency/unit; fail or mark unknown rather than infer scale from values. [evidence: unit tests]
- [ ] 7.7 Add `publication_time_status` and `historical_as_of_eligible` metadata. Default to unknown/false unless a defensible publication timestamp is verified. [evidence: no-lookahead tests]
- [ ] 7.8 Do not substitute fiscal period end for publication/available-from time. [evidence: temporal-boundary tests]
- [ ] 7.9 Preserve restatement/version identity only when supplied; otherwise disclose that revisions cannot be historically reconstructed from FiinQuantX alone. [evidence: version tests]
- [ ] 7.10 Test manufacturing, securities, banking and insurance shapes; annual/quarterly; consolidated/separate; audited/unaudited; missing fields and entitlement-limited ratios. [evidence: focused suite]
- [ ] 7.11 Document that FiinQuantX alone does not complete publication-aware fundamentals issue #87 unless publication-time enrichment is added. [evidence: provider and downstream docs]

## 8. FQ-5 namespaced vendor analytics

- [ ] 8.1 Add `screening.vendor` only after dynamic filter/column, date and entitlement behavior are verified. [evidence: contract tests]
- [ ] 8.2 Add `analytics.vendor_index_contribution` for `MoneyFlow.get_contribution()` only as vendor-derived output. [evidence: contract tests]
- [ ] 8.3 Add `indicator.vendor_derived` only for reviewed indicator methods and metadata; do not silently replace deterministic OpenStock features or scores. [evidence: policy tests]
- [ ] 8.4 Exclude `Rebalance`, allocation quantities, strategy/execution helpers and predictive marketing helpers from the provider MVP. [evidence: capability and forbidden-member tests]

## 9. FQ-6 streaming architecture follow-up

- [ ] 9.1 Create a separate OpenSpec/change before implementing `Trading_Data_Stream`, realtime `Fetch_Trading_Data`, `BidAsk` or order-book-change subscriptions. [depends: FQ-1 foundation]
- [ ] 9.2 Define subscription, event, callback, reconnect, ordering, backpressure, shutdown, session and licensed-retention contracts in that change.
- [ ] 9.3 Do not call streaming methods from synchronous `ProviderPlugin.fetch()` or a normal REST request. [evidence: architecture tests]
- [ ] 9.4 Do not label a stream as synchronous `equity.quote`. [evidence: capability tests]

## 10. Documentation, service and operator surfaces

- [x] 10.1 Add `vnstock/docs/providers/FIINQUANTX.md` with secure installation, credentials, enabled datasets, limitations, contract versions and license controls. [evidence: `vnstock/docs/providers/FIINQUANTX.md` at `0bd6a5d`]
- [ ] 10.2 Update provider hardening and plugin architecture status documentation.
- [ ] 10.3 Expose only safe install/auth/access/health/version metadata through existing provider metadata endpoints. [evidence: capability status is exposed at `0bd6a5d`; complete operator metadata contract remains pending]
- [x] 10.4 Do not add FiinQuantX REST login/logout or raw-secret endpoints. [evidence: forbidden-route tests and HTTP smoke at `0bd6a5d`]
- [ ] 10.5 Add bounded explicit-source examples that never print credentials, session objects or raw auth payloads.

## 11. Validation

- [x] 11.1 Add offline provider protocol/conformance tests. [evidence: focused provider tests at `0bd6a5d`]
- [x] 11.2 Add dataset contract and versioned normalizer tests for every enabled capability. [evidence: provider, contract and service tests at `0bd6a5d`]
- [ ] 11.3 Add documentation-inconsistency regression fixtures: timestamp variants, field casing, return-object variants, `fb/fs` direction and free-float unit.
- [ ] 11.4 Add auth, access, version, limits, schema, empty-result, secret-redaction, forbidden-member and runtime-path tests.
- [x] 11.5 Add opt-in bounded live tests guarded by `VNSTOCK_LIVE_TESTS`, `VNSTOCK_LIVE_PROVIDERS=FIINQUANTX` and licensed acknowledgement. [evidence: `tests/live/providers/test_fiinquantx_live.py` at `0bd6a5d`]
- [x] 11.6 Ensure live tests record only SDK version, method, shape, row count, hashes and safe statuses, not raw licensed rows. [evidence: live test assertions and redacted run at `0bd6a5d`]
- [x] 11.7 Run targeted FiinQuantX unit/contract tests. [evidence: focused suite at `0bd6a5d`]
- [ ] 11.8 Run all provider, auth, router, runtime, service, quality and contract tests.
- [x] 11.9 Run Ruff check and format check for `vnstock`. [evidence: focused Ruff checks at `0bd6a5d`]
- [x] 11.10 Build/install base `vnstock` without FiinQuantX. [evidence: `vnstock-service:base-check` at `0bd6a5d`]
- [ ] 11.11 Run approved-version package/runtime checks in the licensed environment. [evidence: exact-version live smoke at `0bd6a5d`; approval evidence remains pending]
- [x] 11.12 Run strict OpenSpec validation. [evidence: `openspec validate fiinquantx-provider-integration --strict` at `0bd6a5d`]
- [x] 11.13 Record exact OpenStock SHA, SDK version, Python/OS, commands, outcomes, enabled methods and live-request scope in `validation.md`. [evidence: validation ledger for `0bd6a5d`]

## Phase gates

- [x] G0A Detailed documentation inventory and exclusion boundary are recorded from PR #103 docs. [evidence: `source-review.md`, `proposal.md`, `design.md`]
- [ ] G0B Licensed runtime, entitlement, unit, timestamp, return-shape, limit and commercial-policy verification passes.
- [ ] G1 Optional provider foundation, auth/session, versioning, access, limits, runtime routing, diagnostics and redaction pass.
- [ ] G2 Reference, OHLCV and price-limit contracts pass without inventing quote, full-universe or historical-membership capability.
- [ ] G3 Flow, ownership, investor, market-cap, free-float, breadth-snapshot and valuation contracts pass where verified.
- [ ] G4 Period-aware fundamentals pass shape/unit tests and explicitly remain historical-as-of ineligible without publication time.
- [ ] G5 Namespaced vendor analytics pass without replacing OpenStock deterministic logic or introducing allocation semantics.
- [ ] G6 Streaming remains deferred or is implemented only under a separately accepted streaming OpenSpec.
- [ ] G7 Full offline regression, package tests, bounded licensed live smoke and strict OpenSpec evidence are attached to the exact implementation commit.
