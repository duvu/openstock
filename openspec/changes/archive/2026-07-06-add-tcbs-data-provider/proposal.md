## Why

`vnstock` currently has overlapping market-data providers for OHLCV and price board data, but TCBS offers a differentiated public/unofficial data surface that can strengthen the data foundation for scanner, research, and ingestion workflows.

Discovery found multiple independent references to TCBS public/unofficial endpoints under:

```text
https://apipubaws.tcbs.com.vn
```

The TCBS data surface appears to include:

- historical OHLCV data
- intraday trading data
- price board / quote snapshot data
- company overview and profile
- symbol industry fields
- foreign ownership percentage
- shareholders, insider deals, subsidiaries, officers, events, news, and dividends
- balance sheet, income statement, cash flow, and financial ratios
- stock screener fields including liquidity, technical, valuation, relative-strength, and foreign-flow indicators

This fills several gaps in the current provider set:

- DNSE is strong for OHLCV and price board but does not currently expose symbol industry or company/fundamental data.
- VCI exposes ICB industry data but TCBS can provide a second industry/reference source.
- KBS provides market/reference coverage but TCBS adds useful derived screener and rating fields.
- Current scanner-readiness work needs stronger reference, industry, valuation, momentum, liquidity, and foreign-flow features.

## What Changes

Add an implementation plan for a data-only TCBS provider.

Initial MVP scope:

- `vnstock/explorer/tcbs/quote.py`
  - OHLCV history
  - intraday trades where public endpoint is verified
- `vnstock/explorer/tcbs/trading.py`
  - price board / quote snapshot
- `vnstock/explorer/tcbs/company.py`
  - company overview
  - company profile
  - large shareholders
  - insider dealing
  - subsidiaries
  - officers
  - events/news
  - activity news
  - dividends
- `vnstock/explorer/tcbs/fundamental.py`
  - balance sheet
  - income statement
  - cash flow
  - financial ratios
- `vnstock/explorer/tcbs/screener.py`
  - stock screener, initially experimental
- `vnstock/explorer/tcbs/const.py`
  - endpoint constants
  - raw-to-normalized field maps
  - interval maps
  - screener field maps

Provider integration:

- Register TCBS in provider capability declarations.
- Add TCBS source support to relevant API/UI paths where compatible.
- Add contract fixtures for raw and normalized responses.
- Add live smoke tests guarded by `VNSTOCK_LIVE_TESTS=true`.
- Add quality validation integration for OHLCV and price board outputs.
- Add docs and provider matrix entries.

## Non-Goals

This change MUST NOT implement:

- broker login
- account APIs
- portfolio APIs
- cash/stock transfer APIs
- order placement, order cancel/modify, or trading execution
- iCopy subscription or copy-trading actions
- customer-private APIs
- strategy, recommendation, or automatic buy/sell logic

TCBS fields such as `tcbs_recommend`, `tcbs_buy_sell_signal`, `stockRating`, valuation labels, or technical-signal labels are vendor-derived signals. They MUST be exposed as `vendor_screener`, `vendor_rating`, or `vendor_signal` fields, not as investment advice and not as raw market data.

## Evidence

Known documented/reverse-documented endpoint groups:

```text
/tcanalysis/v1/ticker/{symbol}/overview
/tcanalysis/v1/company/{symbol}/overview
/tcanalysis/v1/company/{symbol}/large-share-holders
/tcanalysis/v1/company/{symbol}/insider-dealing
/stock-insight/v1/company/{symbol}/subsidiaries
/stock-insight/v1/company/{symbol}/officers
/tcanalysis/v1/ticker/{symbol}/events-news
/tcanalysis/v1/ticker/{symbol}/activity-news
/stock-insight/v1/company/{symbol}/dividends
/stock-insight/v1/finance/{symbol}/balance-sheet
/stock-insight/v1/finance/{symbol}/income-statement
/stock-insight/v1/finance/{symbol}/cash-flow
/stock-insight/v1/finance/{symbol}/financialratio
/stock/v2/stock/bars-long-term
/stock/v1/intraday/{symbol}/his/paging
/stock/v1/stock/second-tc-price
/ligo/v1/watchlist/preview
```

Additional open-source implementations use variants:

```text
/stock-insight/v1/stock/bars-long-term
/stock-insight/v2/stock/bars-long-term
```

The implementation MUST verify actual availability with live smoke tests before TCBS is treated as a reliable provider.

## Impact

Affected areas:

- `vnstock/explorer/tcbs/`
- `vnstock/api/quote.py`
- `vnstock/api/trading.py`
- `vnstock/api/company.py`
- `vnstock/api/fundamental.py`
- `vnstock/api/listing.py`
- `vnstock/ui/_registry.py`
- `vnstock/core/provider/capabilities.py`
- `vnstock/core/quality/`
- `tests/contracts/providers/`
- `tests/live/providers/`
- `tests/fixtures/providers/tcbs/`
- `docs/PROVIDER_HARDENING.md`
- `docs/DATA_QUALITY.md`
- `roadmap.md`

## Rollout

1. Implement TCBS explorer adapters behind explicit `source="TCBS"` usage.
2. Add fixtures and contract tests before exposing broad Unified UI paths.
3. Add live smoke tests and mark TCBS health unknown/degraded until live endpoints pass.
4. Expose stable datasets first: OHLCV, price board, company overview, financial ratios.
5. Keep screener experimental until field stability and semantics are documented.
