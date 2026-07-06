# TCBS Data Provider Design

## Goals

The TCBS provider must add a reliable data-only adapter for public/unofficial TCBS market, reference, fundamental, and screener data.

The system must:

1. Add TCBS as an explicit provider source.
2. Support historical OHLCV data for equities and, where verified, indices/derivatives.
3. Support price board / quote snapshot data.
4. Support company overview/profile data including industry fields.
5. Support financial statement and financial ratio datasets.
6. Support stock screener data as an experimental vendor-derived dataset.
7. Add provider capability declarations, fixtures, contract tests, and opt-in live smoke tests.
8. Preserve data-only boundaries and exclude broker/account/order/iCopy functionality.
9. Attach provider metadata and quality reports to normalized outputs where applicable.
10. Treat TCBS APIs as unofficial public endpoints that can drift.

## Non-Goals

The TCBS provider must not:

- authenticate into TCBS customer accounts
- store or accept TCBS account credentials
- access portfolio/account/order APIs
- place, cancel, modify, or simulate broker orders
- implement iCopy/copy-trading actions
- bypass rate limits, login walls, CAPTCHAs, or authorization controls
- present vendor-derived ratings/signals as investment advice
- replace KBS/VCI/DNSE as the default provider without explicit evidence and tests

## Proposed Package Structure

```text
vnstock/explorer/tcbs/
├── __init__.py
├── const.py
├── quote.py
├── trading.py
├── company.py
├── fundamental.py
└── screener.py
```

Test and fixture structure:

```text
tests/
├── fixtures/
│   └── providers/
│       └── tcbs/
│           ├── ohlcv_daily_raw.json
│           ├── ohlcv_daily_normalized.parquet
│           ├── price_board_raw.json
│           ├── company_overview_raw.json
│           ├── financial_ratios_raw.json
│           └── screener_raw.json
├── contracts/
│   └── providers/
│       └── test_tcbs_contracts.py
└── live/
    └── providers/
        └── test_tcbs_live.py
```

## Endpoint Catalog

Base URL:

```text
https://apipubaws.tcbs.com.vn
```

### Market Data

Historical OHLCV candidates:

```text
GET /stock/v2/stock/bars-long-term
GET /stock-insight/v2/stock/bars-long-term
GET /stock-insight/v1/stock/bars-long-term
```

Params:

```text
resolution=1|5|15|30|60|D|W|M
ticker=FPT
type=stock|index|derivative
to=<unix seconds>
countBack=<bars>
from=<unix seconds>  # supported by some endpoint variants
```

Intraday candidate:

```text
GET /stock/v1/intraday/{symbol}/his/paging?page=0&size=100
```

Price board candidate:

```text
GET /stock/v1/stock/second-tc-price?tickers=FPT,VCB,TCB
```

### Company / Reference Data

```text
GET /tcanalysis/v1/ticker/{symbol}/overview
GET /tcanalysis/v1/company/{symbol}/overview
GET /tcanalysis/v1/company/{symbol}/large-share-holders
GET /tcanalysis/v1/company/{symbol}/insider-dealing?page=0&size=20
GET /stock-insight/v1/company/{symbol}/subsidiaries?page=0&size=100
GET /stock-insight/v1/company/{symbol}/officers?page=0&size=20
GET /tcanalysis/v1/ticker/{symbol}/events-news?page=0&size=15
GET /tcanalysis/v1/ticker/{symbol}/activity-news?page=0&size=15
GET /stock-insight/v1/company/{symbol}/dividends?page=0&size=15
```

### Fundamental Data

```text
GET /stock-insight/v1/finance/{symbol}/balance-sheet?yearly=true&isAll=true
GET /stock-insight/v1/finance/{symbol}/income-statement?yearly=true&isAll=true
GET /stock-insight/v1/finance/{symbol}/cash-flow?yearly=true&isAll=true
GET /stock-insight/v1/finance/{symbol}/financialratio?yearly=true&isAll=true
```

### Screener / Vendor-Derived Data

```text
POST /ligo/v1/watchlist/preview
```

Payload shape:

```json
{
  "tcbsID": null,
  "filters": [
    {"key": "exchangeName", "operator": "=", "value": "HOSE,HNX,UPCOM"}
  ],
  "size": 50
}
```

## Normalized Data Contracts

### OHLCV

Normalized output:

```text
time
open
high
low
close
volume
```

DataFrame attrs:

```text
source = "TCBS"
symbol
interval
start
end
endpoint_variant
fetched_at
```

The adapter must support endpoint fallback. Fallback order:

```text
1. /stock/v2/stock/bars-long-term
2. /stock-insight/v2/stock/bars-long-term
3. /stock-insight/v1/stock/bars-long-term
```

The adapter must record the successful endpoint in `df.attrs["endpoint_variant"]`.

### Price Board

Minimum normalized output:

```text
symbol
close_price
volume_accumulated
```

Preferred normalized output when fields are present:

```text
symbol
time
close_price
volume_accumulated
price_change
percent_change
foreign_net_volume
foreign_net_percent
rsi
macd_histogram
macd_signal
technical_signal
avg_signal
ma20
ma50
ma100
session_trend
market_weight_3d
market_weight_1m
market_weight_3m
market_weight_1y
relative_strength_3d
relative_strength_1m
relative_strength_3m
relative_strength_1y
relative_strength_avg
high_price_1m
high_price_3m
high_price_1y
low_price_1m
low_price_3m
low_price_1y
percent_from_1y_high
percent_from_1y_low
pe
pb
roe
tcbs_rating
bid_volume
ask_volume
valuation_score
highest_matched_price
market_score
vni_pe
vni_pb
```

Vendor-derived fields must be clearly named and documented.

### Company Overview / Symbol Industry

Normalized output:

```text
symbol
exchange
industry
industry_id
industry_id_v2
company_type
short_name
website
foreign_percent
outstanding_share
issue_share
established_year
employees
stock_rating
```

For symbol industry dataset:

```text
symbol
provider = "TCBS"
classification_system = "TCBS_INTERNAL"
level = null
industry_code = industry_id_v2 or industry_id
industry_name = industry
fetched_at
```

### Financial Statements

Financial statement outputs should preserve raw TCBS line-item names initially and normalize common metadata:

```text
symbol
period_type = year|quarter
year
quarter
report_type = balance_sheet|income_statement|cash_flow|financial_ratio
provider = "TCBS"
fetched_at
```

A later quality contract may standardize accounting line items across KBS/VCI/TCBS.

### Screener

The screener adapter should be explicitly experimental.

Initial normalized fields may include:

```text
symbol
exchange
industry
roe
active_buy_pct
strong_buy_pct
high_vol_match
forecast_vol_ratio
ev_ebitda
revenue_growth_1y
revenue_growth_5y
eps_growth_1y
eps_growth_5y
avg_trading_value_5d
avg_trading_value_10d
avg_trading_value_20d
relative_strength_3d
relative_strength_1m
relative_strength_3m
relative_strength_1y
foreign_vol_pct
foreign_buysell_20s
vol_vs_sma5
vol_vs_sma10
vol_vs_sma20
vol_vs_sma50
price_growth_1w
price_growth_1m
prev_1d_growth_pct
prev_1m_growth_pct
prev_1y_growth_pct
profit_last_4q
pct_1y_from_peak
pct_away_from_hist_peak
pct_1y_from_bottom
pct_off_hist_bottom
vendor_signal_fields_json
```

Fields containing labels in multiple languages must extract the requested language when `lang` is provided and retain raw language objects when `get_all=True`.

## Provider Capability Declarations

Add TCBS capabilities:

```python
ProviderCapability(
    provider="TCBS",
    dataset_type="ohlcv",
    asset_class="equity",
    method="history",
    intervals=["1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"],
    supports_history=True,
    requires_auth=False,
    is_live_testable=True,
    notes="Unofficial public endpoint; endpoint variants require fallback."
)
```

Additional declarations:

```text
price_board / equity / live_snapshot / unauthenticated
company_profile / equity / unauthenticated
symbol_industry / equity / unauthenticated / TCBS_INTERNAL
financial_statement / equity / unauthenticated
financial_ratio / equity / unauthenticated
vendor_screener / equity / unauthenticated / experimental
intraday_trades / equity / unauthenticated if live smoke passes, otherwise auth_unknown
```

## API / Unified UI Integration

Initial explicit-source support:

```python
Market().equity.ohlcv(symbol="FPT", source="TCBS", ...)
Market().equity.quote(symbols_list=["FPT", "VCB"], source="TCBS")
Reference().company.info(symbol="FPT", source="TCBS")
Reference().equity.list_by_industry(source="TCBS")
Fundamental().equity.balance_sheet(symbol="FPT", source="TCBS")
Fundamental().equity.income_statement(symbol="FPT", source="TCBS")
Fundamental().equity.cash_flow(symbol="FPT", source="TCBS")
Fundamental().equity.ratios(symbol="FPT", source="TCBS")
```

Screener should remain explorer-only or experimental until the public API is stable:

```python
from vnstock.explorer.tcbs.screener import Screener

Screener().stock(params={"exchangeName": "HOSE,HNX,UPCOM"}, limit=50)
```

## Quality and Provider Hardening

The TCBS provider must integrate with the current quality/provider hardening layers.

### Contract Tests

Contract tests must verify:

- raw OHLCV fixture parses successfully
- normalized OHLCV has `time/open/high/low/close/volume`
- price board fixture produces required columns
- company overview fixture contains symbol, industry, exchange, and stock rating fields when present
- financial ratio fixture parses without losing period metadata
- screener fixture parses `searchData.pageContent`
- missing top-level `data` or `searchData.pageContent` produces a structured provider error

### Live Smoke Tests

Live tests must be disabled by default and enabled with:

```bash
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_PROVIDERS=TCBS pytest tests/live/providers/test_tcbs_live.py -m live
```

Smoke tests should use a small symbol set:

```text
FPT, VCB, TCB
```

They should test:

- OHLCV daily for a short range
- price board for one to three symbols
- company overview for one symbol
- financial ratios for one symbol
- screener minimal payload
- intraday only if endpoint returns stable public data

### Data Quality

OHLCV and price board outputs must support:

```python
validate=True
quality_mode="warn" | "strict"
```

DataFrames must attach quality report metadata under:

```python
df.attrs["quality"]
```

## Error Handling

Add TCBS-specific provider errors or reuse existing structured provider errors.

Required cases:

- unreachable endpoint
- HTTP 401/403 marks capability as auth-required or blocked
- HTTP 429 marks provider as rate-limited/degraded
- missing `data` key for OHLCV
- empty `data` for valid symbol/date range
- invalid symbol
- malformed screener response
- unsupported interval
- unsupported asset type
- endpoint variant fallback exhausted

## Rate Limit Policy

TCBS endpoints are unofficial public endpoints. The implementation must:

- send browser-like user-agent headers
- avoid high-concurrency defaults
- set conservative request timeout
- respect retry/backoff policy
- allow rate limiter integration later
- keep live smoke tests small
- not run live TCBS tests in default CI

## Migration / Backward Compatibility

No existing behavior should change by default.

TCBS should only be used when:

```python
source="TCBS"
```

or when a future router/fallback explicitly selects TCBS because capability and health are proven.

## Open Questions

- Which OHLCV endpoint variant is currently most stable: `stock/v2`, `stock-insight/v2`, or `stock-insight/v1`?
- Does intraday endpoint consistently work without auth outside market hours?
- Which TCBS screener fields are stable enough for a normalized schema?
- Should `stockRating`, `tcbs_recommend`, and `tcbs_buy_sell_signal` be exposed only in an experimental namespace?
- Should TCBS_INTERNAL industry be mapped to VCI ICB later, or remain a separate classification system?
