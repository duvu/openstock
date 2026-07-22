# FiinQuantX licensed probe summary — 2026-07-22

This is a sanitized summary of a local licensed probe. It contains no account
identifier, credential, session state, vendor response body, or licensed row
value. The machine-readable full report remains outside the repository under
the operator's control.

## Runtime

| Field | Value |
| --- | --- |
| SDK | `fiinquantx==0.1.64` (`INSTALLED_SUPPORTED`) |
| Python | `3.11.15` |
| Platform | Linux x86_64 / glibc 2.41 |
| Account scope | `LICENSED_LOCAL_ACCOUNT` |
| Per-call bound | 15 seconds; isolated spawned worker |

## Bounded synchronous method evidence

| SDK method | Candidate dataset(s) | Outcome | Safe response shape / disposition |
| --- | --- | --- | --- |
| `TickerList` | index and sector membership | success | iterable, 30 representative index members |
| `BasicInfor` | company information | entitlement | unavailable to this local account |
| `Fetch_Trading_Data` | equity OHLCV | success | two rows; `ticker,timestamp,open,high,low,close,volume,value` |
| `PriceStatistics.get_overview` | market cap, liquidity | valid empty | no rows for the bounded representative window |
| `PriceStatistics.get_foreign` | foreign flow, ownership | valid empty | no rows for the bounded representative window |
| `PriceStatistics.get_freefloat` | free-float observation | success | two rows; fields require separate unit/semantics work (#360) |
| `PriceStatistics.get_ceilingfloor` | price limits | valid empty | no rows for the bounded representative window |
| `PriceStatistics.get_value_by_investor` | investor flow | valid empty | no rows for the bounded representative window |
| `MarketBreadth.get` | market breadth | entitlement | unavailable to this local account |
| `MarketDepth.get_stock_valuation` | stock valuation | success | two rows; `ticker,timestamp,pe,pb` |
| `MarketDepth.get_sector_valuation` | sector valuation | valid empty | no rows for the bounded representative window |
| `MarketDepth.get_index_valuation` | index valuation | success | two rows; `ticker,timestamp,pe,pb` |
| `FundamentalAnalysis.get_financial_statement` | balance sheet | success | list outer shape, one item; mapping remains deferred (#365) |
| `FundamentalAnalysis.get_ratios` | financial ratios | success | list outer shape, one item; mapping remains deferred (#365) |

`MarketDepth` order-book snapshots and the realtime subscription candidates
were not invoked: no accepted bounded synchronous order-book signature or
streaming lifecycle exists for them.

## Existing foundation certification

The provider's four enabled datasets were called through their canonical plugin
paths, not by replaying raw vendor payloads.

| Dataset | Certified bounded observation |
| --- | --- |
| `equity.ohlcv` | A two-session `2026-07-01` through `2026-07-02` range returned two ascending, inclusive session dates. A two-bar count-back request returned two ascending bars. |
| `index.ohlcv` | The same range and count-back invariants passed for the representative index. |
| `reference.index_membership_snapshot` | 30 rows; canonical `entity_id,member_symbol,observed_at`; UTC `observed_at`; `observed_current_membership`. |
| `reference.sector_membership_snapshot` | 28 rows; the same canonical current-snapshot contract. |

The canonical OHLCV request is daily, `adjusted=False` and `lasted=False`.
FiinQuantX documents `lasted=False` as excluding the unfinished last candle.
The normalized timestamp is a timezone-naive session timestamp; it is used as a
trading session date, not an instant. The provider documents `volume` as
trading/matched volume and `value` as trading value, but does not state a
currency scale for `value`. OpenStock therefore keeps the vendor numeric field
without asserting a currency unit or using it for currency arithmetic.

## Warehouse persistence acceptance

An initialized, mode-0700 temporary `vnalpha` warehouse received two identical
strict service requests for the bounded representative equity window. Each
ingestion run retained its two raw observations and its own ingestion lineage
(four raw audit rows total). Building canonical OHLCV twice then produced two
canonical keys, not four; both retained `FIINQUANTX` provenance and
`RAW_UNADJUSTED` basis. This is the intended split: immutable raw provenance is
run-scoped, while the provider-independent canonical key is idempotent.

Two strict index-membership requests similarly persisted distinct current
observations (two 30-member snapshots) with SDK/contract lineage and
`observed_current_membership`. They are not deduplicated because an observation
time and request identity are evidence, not historical effective dates.

## Negative evidence and defer rule

Valid-empty and entitlement outcomes are distinct successful probe outcomes,
not permission to expose a candidate dataset. All candidates outside the four
existing foundations remain `DEFERRED` until their canonical schema, units,
point-in-time semantics, revision behavior and named consumer are separately
verified.

## Vertical decisions

| Issue | Decision from this probe | Resulting capability state |
| --- | --- | --- |
| #360 reference, taxonomy and free float | Keep the existing mixed-provider universe boundary. `BasicInfor` is entitlement-limited; free-float has only an outer shape and no verified unit/point-in-time semantics. | No new route or persistence; candidates remain `DEFERRED`. |
| #361 market cap, limits and liquidity | The representative overview and ceiling/floor calls were valid-empty. | No new route or persistence; candidates remain `DEFERRED`. |
| #362 flow and ownership | The representative foreign and investor calls were valid-empty. | No new route or persistence; candidates remain `DEFERRED`. |
| #363 breadth and depth | Breadth is entitlement-limited; no accepted synchronous order-book method was found. | No new route or persistence; candidates remain `DEFERRED`. |
| #364 valuation | Stock and index valuation outer schemas exist, but methodology, units, index/sector boundary and revision semantics are not verified. | No new route or persistence; candidates remain `DEFERRED`. |
| #365 fundamentals | Statements and ratios return one-item lists, but inner field mapping, units and publication/revision time are not verified. | No new route or persistence; candidates remain `DEFERRED`. |
| #366 realtime | No subscription lifecycle was invoked or exposed: it requires separate event-time, sequence, reconnect and stop evidence. | `STREAMING` candidates remain `DEFERRED`. |
