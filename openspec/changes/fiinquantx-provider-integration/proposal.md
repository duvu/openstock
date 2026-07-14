# Proposal: FiinQuantX Provider Integration

## Summary

Add FiinQuantX as the first prioritized commercial, authenticated data provider in the `vnstock` data platform.

The provider must integrate through the existing plugin/runtime architecture and must remain data-only. It may supply licensed Vietnamese market, reference, foreign-flow, valuation, and fundamental datasets, but it must not expose broker, account, order, portfolio, margin, transfer, or execution capabilities.

Because the official public repository distributes wheels without public source or API contracts, implementation begins with a mandatory licensed SDK contract-discovery gate. No method, schema, capability, or entitlement may be guessed.

## Motivation

The existing provider set gives OpenStock useful public-market redundancy, but important research datasets remain incomplete or weakly authoritative:

- publication-aware financial statements and ratios;
- historical foreign trading flows;
- index constituent and free-float history;
- outstanding-share and market-cap history;
- valuation history;
- market breadth and sector/reference metadata;
- commercial-quality intraday data where licensed.

FiinQuantX is maintained by FiinQuant and distributed as a Python wheel through the official `fiinquant/fiinquantx` repository. At the reviewed commit, the package index lists version `0.1.64`. The repository does not expose source code, method signatures, schemas, or license terms, so a production adapter requires licensed documentation and runtime discovery before coding.

## Priority

```text
Priority: P0
```

This is the highest-priority new provider integration because the user has chosen to pay for a commercial source and intends to use it as an authoritative research-data input.

## Scope

### Provider foundation

- optional FiinQuantX SDK dependency;
- lazy import and installation diagnostics;
- authenticated credential/session integration;
- entitlement-aware capability declarations;
- provider-specific quota, connection, and cooldown diagnostics;
- `ProviderPlugin` implementation;
- registration in the built-in plugin registry;
- routing through `PluginRuntime` only;
- stable `DataResult` metadata and redaction.

### Initial dataset families

The implementation shall prioritize verified FiinQuantX capabilities in this order:

1. existing canonical market/reference contracts:
   - `reference.symbols`;
   - `equity.ohlcv`;
   - `index.ohlcv`;
   - `equity.quote` where verified;
2. market-structure and ownership datasets:
   - `foreign_flow.daily`;
   - index constituents;
   - free-float history;
   - outstanding-share history;
   - foreign ownership/room history;
   - market-cap history;
   - market breadth;
   - valuation history;
3. structured fundamentals:
   - `fundamental.balance_sheet`;
   - `fundamental.income_statement`;
   - `fundamental.cash_flow`;
   - `fundamental.financial_ratio`;
4. optional later datasets:
   - intraday bars;
   - order-book snapshots;
   - aggressor/buy-sell flow;
   - vendor-derived indicators.

A dataset enters the provider capability matrix only after its licensed SDK method, entitlement, parameters, raw schema, canonical mapping, and contract tests are verified.

## Capabilities

### New capability

- `fiinquantx-provider-integration`: licensed FiinQuantX SDK integration through the `vnstock` provider platform.

### Modified platform capabilities

- provider plugin registry;
- auth-aware routing;
- dataset contracts;
- provider diagnostics and capability matrix;
- rate/quota controls;
- service runtime response metadata;
- provider fixture, contract, and live-smoke testing.

## Non-goals

- No reverse engineering or direct undocumented HTTP endpoint integration.
- No web scraping of FiinQuant or FiinQuantX pages.
- No redistribution of the FiinQuantX wheel, licensed documentation, or raw licensed records.
- No public SaaS exposure of licensed datasets without explicit commercial permission.
- No broker login, account, order, portfolio, allocation, margin, transfer, execution, or automated trading behavior.
- No automatic replacement of existing providers before comparison and fallback policy is validated.
- No silent use of vendor-derived indicators as canonical OpenStock scoring logic.

## Source authority and fallback stance

FiinQuantX may become the preferred provider for dataset families where its licensed feed is more authoritative or complete, especially fundamentals, foreign flows, index structure, and valuation.

KBS, VCI, DNSE, TCBS, MSN, FMP, and FMARKET remain available according to their actual capabilities. Existing providers shall not be removed by this change.

For overlapping datasets, routing policy must be explicit:

```text
explicit source=FIINQUANTX
  -> use FiinQuantX or return a typed installation/auth/entitlement failure

source=auto
  -> choose according to dataset capability, configured priority, entitlement,
     provider health, quota budget, freshness, and fallback policy
```

## Commercial and deployment boundary

The integration must include a documented license-decision matrix before enabling persistence or service exposure.

Default safeguards:

- credentials supplied only through the existing credential system or environment references;
- no credentials in logs, exceptions, diagnostics, fixtures, DataFrame attributes, API responses, notebooks, or MCP inputs;
- local-only service exposure unless the agreement permits redistribution;
- synthetic offline fixtures;
- opt-in live tests;
- raw archive and bulk export disabled unless explicitly permitted.

## Dependencies

Depends on the implemented `vnstock` plugin foundation:

- `ProviderPlugin`;
- `PluginRegistry`;
- `PluginRouter`;
- `PluginRuntime`;
- `DataResult`;
- dataset contracts;
- auth-aware provider selection;
- provider diagnostics and contract tests.

The provider can be implemented independently from unfinished `vnalpha` intelligence tickets. Downstream fundamental, corporate-action, foreign-flow, regime, and sector work may consume the new datasets after the provider contracts are accepted.

## Delivery slices

```text
FQ-0  licensed SDK and license contract discovery
FQ-1  provider/auth/entitlement/runtime foundation
FQ-2  reference and EOD market datasets
FQ-3  foreign flow, index structure, breadth, and valuation
FQ-4  publication-aware fundamentals
FQ-5  optional intraday/order-book/vendor indicators
```

FQ-0 is a hard gate. FQ-1 must not advertise unverified datasets. Each later slice may be delivered and validated independently.

## Success criteria

- FiinQuantX is installable as an optional provider without breaking base `vnstock` installation.
- Missing SDK, invalid credentials, expired entitlement, quota exhaustion, unsupported datasets, and provider errors produce typed, sanitized outcomes.
- All service fetches use `PluginRuntime`.
- Capability declarations match the licensed SDK and tested entitlement.
- Canonical datasets preserve provider, fetch time, source period/date, quality, and diagnostic lineage.
- Offline tests use synthetic fixtures; live tests are explicitly gated.
- Existing providers remain backward compatible.
- The **read-only research boundary** remains intact.