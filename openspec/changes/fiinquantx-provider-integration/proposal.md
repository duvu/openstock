# Proposal: FiinQuantX Data Provider Integration

## Summary

Integrate the licensed FiinQuantX SDK into `vnstock` as the prioritized commercial Vietnamese market-data provider.

The integration SHALL use the existing `ProviderPlugin` / `PluginRegistry` / `PluginRouter` / `PluginRuntime` architecture and SHALL remain strictly data-only. It may expose documented reference, market, flow, valuation and structured fundamental data. It SHALL NOT expose any FiinQuantX broker, account, financing, order, position, portfolio or execution functionality.

## Evidence basis

This proposal is based on two sources:

```text
Official package repository:
  fiinquant/fiinquantx @ abb1e038
  latest indexed wheel: fiinquantx 0.1.64

Detailed documentation mirror committed to OpenStock:
  docs commit: 30b684d48911a3e0cf6e7c98fac6a2aa2b790f24
  merged PR: #103
  canonical API reference: docs/fiinquant/site/
```

The detailed mirror documents real SDK classes, methods, parameters and sample schemas. A licensed runtime probe is still required before enabling capabilities because the package is binary-only, account entitlements vary, and the documentation contains several version/type inconsistencies.

## Priority

```text
Priority: P0
```

FiinQuantX is the first commercial provider to prioritize because it fills material gaps in OpenStock:

- historical foreign flow and ownership/room;
- domestic individual, institutional and proprietary trading flow;
- current index/sector membership and ICB reference;
- market-cap and free-float series;
- stock, sector and index valuation history;
- market-breadth snapshots;
- structured financial statements and ratios;
- commercial intraday and order-book data for a later streaming phase.

## Verified documented API surface

### Authentication

```python
from FiinQuantX import FiinSession
client = FiinSession(username=username, password=password).login()
```

Credentials SHALL be sourced from the existing local credential/auth layer, not from data method parameters or service requests.

### Synchronous APIs in scope

| SDK surface | Documented purpose | Proposed canonical use |
|---|---|---|
| `TickerList(ticker=...)` | Current index or ICB-sector members | `reference.index_membership_snapshot`, `reference.sector_membership_snapshot` |
| `BasicInfor(...).get()` | Company, exchange and ICB levels | `reference.company_info` |
| `Fetch_Trading_Data(realtime=False, ...).get_data()` | Historical EOD/intraday OHLCV, value, aggressive and foreign flow | `equity.ohlcv`, `index.ohlcv`, optional flow contracts |
| `PriceStatistics().get_overview(...)` | Market-cap and trading statistics by period | `market.market_cap_history`, optional market statistics |
| `PriceStatistics().get_foreign(...)` | Foreign flow, ownership and room | `foreign_flow.daily`, `foreign_ownership.daily` |
| `PriceStatistics().get_freefloat(...)` | Free-float series | `reference.free_float_history` after unit verification |
| `PriceStatistics().get_ceilingfloor(...)` | Daily floor/ceiling prices | `market.price_limits.daily` |
| `PriceStatistics().get_value_by_investor(...)` | Domestic/foreign/proprietary investor flow | `investor_flow.daily` |
| `MarketDepth().get_*_valuation(...)` | Stock, sector and index P/E/P/B | separate valuation contracts by entity scope |
| `MarketBreadth().get(...)` | Current breadth snapshot | `market.breadth_snapshot` |
| `FundamentalAnalysis().get_financial_statement(...)` | Nested annual/quarterly statements | existing fundamental statement contracts |
| `FundamentalAnalysis().get_ratios(...)` | Financial ratios by period and consolidation scope | `fundamental.financial_ratio` |
| `StockScreening().get(...)` | Vendor screening query with dynamic fields | later `screening.vendor` capability |
| `MoneyFlow().get_contribution(...)` | Vendor index-contribution analytics | later `analytics.vendor_index_contribution` |

### Streaming APIs documented but deferred

```text
Trading_Data_Stream
Fetch_Trading_Data(realtime=True)
BidAsk
```

The current `PluginRuntime.fetch()` and local REST service are synchronous and do not define subscription lifecycle, callback backpressure, reconnection, sequence or WebSocket contracts. Streaming SHALL be delivered through a separate architecture slice/change rather than disguised as synchronous fetch.

## Revised scope

### Slice FQ-0A — Documentation contract inventory

Completed by this OpenSpec update:

- verified installation and login syntax;
- verified documented synchronous and streaming SDK surfaces;
- recorded documented parameters and field families;
- recorded documentation inconsistencies and unresolved runtime questions;
- identified and excluded all trading/account methods.

### Slice FQ-0B — Licensed runtime and commercial-policy verification

Required before enabling the provider:

- install and probe the approved SDK version;
- verify Python compatibility, return object types, fields and dtypes;
- verify auth/session failure behavior;
- verify entitlements and package-specific field availability;
- verify limits, connection counts and quotas;
- verify timestamps, timezone, adjustment and unit conventions;
- verify commercial permissions for cache, persistence, derived data and local service exposure.

### Slice FQ-1 — Optional provider foundation

- lazy SDK loading;
- secure version compatibility policy;
- `FiinQuantXProviderPlugin`;
- local credential/session adapter;
- implemented-capability and runtime-entitlement checks;
- typed, sanitized provider errors;
- safe diagnostics;
- registration in the built-in plugin registry;
- synchronous fetches through `PluginRuntime` only.

### Slice FQ-2 — Reference and historical market data

Initial synchronous contracts:

```text
equity.ohlcv
index.ohlcv
reference.company_info
reference.index_membership_snapshot
reference.sector_membership_snapshot
```

Optional after runtime verification:

```text
reference.symbols
market.price_limits.daily
```

`reference.symbols` SHALL NOT be advertised merely by unioning a few documented index lists. A complete universe and asset classification must be verified.

A synchronous `equity.quote` capability is not included in this slice because only realtime streaming is documented.

### Slice FQ-3 — Flow, ownership and market structure

```text
foreign_flow.daily
foreign_ownership.daily
investor_flow.daily
market.market_cap_history
reference.free_float_history
market.breadth_snapshot
valuation.stock.daily
valuation.sector.daily
valuation.index.daily
```

Each contract SHALL define unit, sign, timestamp, entity scope, uniqueness, aggregation frequency and revision semantics independently.

Direct historical outstanding-share data is not documented. It SHALL remain unsupported until verified through an SDK method or an approved raw field.

### Slice FQ-4 — Period-aware structured fundamentals

```text
fundamental.balance_sheet
fundamental.income_statement
fundamental.cash_flow
fundamental.financial_ratio
```

The adapter SHALL preserve:

```text
ticker
year
quarter
statement type
consolidated/separate scope
audited flag
company type
nested vendor field path
currency/unit when verified
```

The FiinQuantX documentation does not expose a publication timestamp or restatement identity. Therefore this slice is **period-aware**, not publication-aware.

Every normalized record SHALL include:

```text
publication_time_status=unknown|verified
historical_as_of_eligible=false unless a defensible available-from timestamp exists
```

FiinQuantX fundamentals alone SHALL NOT satisfy publication-aware issue #87 or historical no-lookahead requirements. Those require source enrichment or another authoritative publication-date source.

### Slice FQ-5 — Namespaced vendor analytics

Potential capabilities:

```text
screening.vendor
indicator.vendor_derived
analytics.vendor_index_contribution
```

These outputs SHALL remain explicitly vendor-derived and SHALL NOT silently replace OpenStock deterministic formulas, screens, ranking or scoring.

The documented `Rebalance` function is excluded from the initial scope because it calculates share quantities for a budget and creates allocation/execution ambiguity.

### Slice FQ-6 — Separate streaming architecture

A later change may integrate:

```text
Trading_Data_Stream
Fetch_Trading_Data(realtime=True)
BidAsk
OrderBook change analytics where demonstrably data-only
```

That change must define:

- subscription lifecycle;
- callback/event envelope;
- async boundary;
- reconnection and resubscription;
- ordering and sequence semantics;
- backpressure and bounded buffers;
- market-session behavior;
- licensed retention;
- shutdown and resource cleanup;
- service WebSocket policy if exposed.

## Explicit exclusions

The following documented SDK areas SHALL NOT enter the `vnstock` provider:

```text
broker login
account information
loan/funding information
cash or buying power
order book used for order placement
create/update/cancel order
order list
positions
close derivative deal
portfolio allocation or execution
```

The provider implementation SHALL use a positive allowlist of approved data classes and methods. Architecture tests SHALL fail if section-7 trading/account SDK members are imported or called.

This exclusion preserves the **read-only research boundary**.

## Contract and normalization policy

The mirror documents several inconsistencies that must fail closed until probed:

- documentation release `0.1.60` versus indexed package `0.1.64`;
- timestamp represented as both string and integer;
- PascalCase, camelCase and snake_case field names;
- conflicting descriptions for `fb` and `fs` on one page;
- direct DataFrame returns versus `.get_data()` examples;
- unclear `freefloat` unit;
- no documented publication timestamp for fundamentals.

The provider SHALL use a versioned normalizer and contract fixtures for each approved SDK version. Unknown shape or unit drift must produce a typed schema failure; it must not be guessed.

## Source authority and routing

For explicit source selection:

```text
source=FIINQUANTX
→ use FiinQuantX or return a typed sanitized failure
→ never silently fall back
```

For auto selection:

```text
source=auto
→ consider implemented capability, auth, entitlement, health, cooldown,
  commercial priority, quota budget, freshness and deployment policy
```

FiinQuantX may become preferred for fundamentals, foreign flow, investor flow, valuation and commercial market structure after validation. Existing KBS, VCI, DNSE, TCBS, MSN, FMP and FMARKET providers remain intact.

## Commercial and security boundary

Before normalized persistence or service exposure is enabled, a reviewed decision record SHALL cover:

```text
in-memory cache
SQLite cache
raw payload storage
normalized local persistence
DuckDB/Postgres sinks
local REST responses
multi-user/public exposure
bulk export
synthetic fixtures
derived analytics
```

Defaults until permission is confirmed:

- no raw payload archive;
- no licensed production rows in Git;
- no bulk export;
- no public or multi-user service exposure;
- local credentials only;
- synthetic offline fixtures;
- live tests opt-in and bounded.

## Success criteria

- Base `vnstock` installs, imports and builds without FiinQuantX.
- Approved SDK version is pinned/verified without vendoring the wheel.
- `FiinSession` credentials remain outside data requests and outputs.
- Every enabled synchronous capability has documented method evidence, live shape verification, a canonical contract, versioned normalizer, synthetic fixture and contract test.
- Section-7 trading/account APIs are unreachable from provider code.
- FiinQuantX fetches use `PluginRuntime` only.
- Explicit-source behavior never silently falls back.
- Fundamentals expose their publication-time limitation honestly.
- Streaming remains deferred until a real streaming platform contract exists.
- Existing providers remain backward compatible.
- The **read-only research boundary** remains intact.