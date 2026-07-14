# Source review: FiinQuantX

## Reviewed sources

### Official package repository

```text
Repository: https://github.com/fiinquant/fiinquantx
Commit: abb1e038f3e7401ab770067c5d7a539a06823097
```

Verified:

- the public repository is a binary wheel-distribution repository, not an open-source SDK repository;
- `README.md` contains only the project name;
- `docs/simple/fiinquantx/index.html` is a package index;
- the newest listed wheel at the reviewed commit is `fiinquantx-0.1.64-py3-none-any.whl`.

### Documentation mirror committed to OpenStock

```text
OpenStock docs commit: 30b684d48911a3e0cf6e7c98fac6a2aa2b790f24
Merged by PR: #103
Canonical mirror: docs/fiinquant/site/
Summary guides: docs/fiinquant/00-*.md through 12-*.md
```

`docs/fiinquant/site/` is the implementation reference because it mirrors the detailed documentation pages, including method names, parameters, field tables and examples. The top-level summary guides are useful for orientation but SHALL NOT be treated as authoritative method contracts when they differ from the mirror.

A concrete discrepancy exists: summary guides use explanatory names such as `get_symbols_by_index()`, while the detailed mirror documents the actual SDK call `TickerList(ticker="VN30")`.

## Verified installation and authentication surface

### Installation

```bash
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

The implementation SHALL NOT vendor or redistribute the wheel. Before adopting the documented `--extra-index-url` command in automation, the implementation SHALL define a secure package-installation policy using an approved version and integrity control. This is required to reduce dependency-confusion and unexpected-upgrade risk.

### Authentication

```python
from FiinQuantX import FiinSession

client = FiinSession(
    username=username,
    password=password,
).login()
```

Documented credential environment names are:

```text
FIINQUANT_USERNAME
FIINQUANT_PASSWORD
```

The summary documentation mentions `FiinQuantX.errors.AuthenticationError`, but the exact exception hierarchy and session expiry/refresh behavior still require licensed runtime verification.

## Verified synchronous data API inventory

The following method inventory is documented strongly enough to design adapters. It is not sufficient by itself to enable a capability; return types, plan entitlements, units, timestamp semantics and version compatibility still require bounded live probes.

### Reference and classification

#### Current index or sector membership

```python
client.TickerList(ticker="VN30")
client.TickerList(ticker="BANKS_L2")
client.TickerList(ticker="8300")
```

Documented behavior:

- accepts index names, sector aliases and ICB codes;
- returns a current list of tickers;
- no effective date, revision date or historical constituent lifecycle is documented.

Therefore this supports current snapshot contracts, not historical index-constituent history.

#### Company and ICB reference

```python
client.BasicInfor(tickers=tickers).get()
```

Documented fields:

```text
ticker
taxCode
organizationName
organizationShortName
exchangeCode
sector
icbNameL1
icbNameL2
icbNameL3
icbNameL4
icbNameL5
```

### Historical and intraday bars

```python
client.Fetch_Trading_Data(
    realtime=False,
    tickers=tickers,
    fields=["open", "high", "low", "close", "volume", "value", "bu", "sd", "fb", "fs", "fn"],
    adjusted=True,
    by="1d",
    period=100,
    # or from_date=...
    to_date=...,
    lasted=False,
).get_data()
```

Documented constraints:

- exactly one of `period` or `from_date` is used;
- documented intervals: `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`;
- tickers may include equities, indices, derivatives and covered warrants;
- `adjusted` controls adjusted versus unadjusted prices;
- `lasted` controls inclusion of the latest incomplete bar.

Documented fields:

```text
ticker
timestamp
open
high
low
close
volume
value
bu   # aggressive-buy volume
sd   # aggressive-sell volume
fb   # foreign-buy value according to the historical-data page
fs   # foreign-sell value according to the historical-data page
fn   # foreign net value
```

Timestamp type, timezone, price scale and adjustment methodology require runtime verification.

### Market statistics and market capitalization

```python
client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date=...,
    to_date=...,
)
```

Documented frequencies:

```text
Daily
Weekly
Monthly
Quarterly
Yearly
```

Documented daily fields include:

```text
ticker
timestamp
percentPriceChange
totalMatchVolume
totalMatchValue
totalDealVolume
totalDealValue
marketCap
```

### Foreign flow, ownership and room

```python
client.PriceStatistics().get_foreign(
    tickers=tickers,
    time_filter="Daily",
    from_date=...,
    to_date=...,
)
```

Documented fields include:

```text
foreignBuyVolumeTotal
foreignSellVolumeTotal
foreignBuyValueTotal
foreignSellValueTotal
foreignNetVolumeTotal
foreignNetValueTotal
foreignBuyVolumeMatched
foreignSellVolumeMatched
foreignBuyValueMatched
foreignSellValueMatched
foreignBuyVolumeDeal
foreignSellVolumeDeal
foreignBuyValueDeal
foreignSellValueDeal
foreignCurrentRoom
foreignTotalRoom
percentForeignTotalRoom
foreignOwned
percentForeignOwned
```

The adapter should separate trading flow from ownership/room rather than place every field into one ambiguous contract.

### Free float

```python
client.PriceStatistics().get_freefloat(
    tickers=tickers,
    from_date=...,
    to_date=...,
)
```

Documented fields:

```text
ticker
timestamp
freefloat
```

The documentation describes `freefloat` as an integer value but elsewhere describes free float as a ratio or index input. Unit semantics must be probed before a canonical contract is enabled.

### Price limits

```python
client.PriceStatistics().get_ceilingfloor(
    tickers=tickers,
    from_date=...,
    to_date=...,
)
```

Documented fields:

```text
ticker
timestamp
floorValue
ceilingValue
```

### Investor-classified trading flow

```python
client.PriceStatistics().get_value_by_investor(
    tickers=tickers,
    from_date=...,
    to_date=...,
)
```

The documented schema includes domestic individual, domestic institutional, foreign individual, foreign institutional and proprietary buy/sell value and volume, with matched/deal breakdowns. It also exposes `openInterest` for derivatives.

This should become a dedicated `investor_flow.daily` contract, not be flattened into generic foreign flow.

### Index contribution analytics

```python
client.MoneyFlow().get_contribution(
    ticker="VNINDEX",
    contribution_day="20Day",
    type="topGainers",
    top=15,
)
```

This is a vendor-derived index-contribution analytic. It is not a historical index-membership source.

### Market breadth snapshot

```python
client.MarketBreadth().get(tickers=[...])
```

Documented fields:

```text
comGroupCode
tradingDate
totalStockUpPrice
totalStockDownPrice
totalStockNoChangePrice
totalStockUnderFloor
totalStockOverCeiling
```

The documented method has no historical date parameters. The initial contract must therefore be a current `market.breadth_snapshot`, not `market.breadth_history`.

### Valuation

```python
client.MarketDepth().get_stock_valuation(tickers, from_date, to_date)
client.MarketDepth().get_sector_valuation(tickers, level, from_date, to_date)
client.MarketDepth().get_index_valuation(tickers, from_date, to_date)
```

Documented fields:

```text
ticker
timestamp
pe
pb
```

Stock, sector and index scope SHALL remain separate canonical contracts because their entity identifiers and methodologies differ.

### Structured financial statements

```python
client.FundamentalAnalysis().get_financial_statement(
    tickers=tickers,
    statement="balancesheet",  # balancesheet | incomestatement | cashflow | full
    years=[2024],
    quarters=[4],               # optional for annual data
    audited=True,
    type="consolidated",        # consolidated | separate
    fields=["Assets.CurrentAssets"],  # optional nested field selection
)
```

Documented metadata:

```text
ticker
year
quarter
reportType
audited
companyType
```

Documented company shapes include manufacturing, securities, banking and insurance. The payload is nested and differs by company type.

No publication timestamp, available-from timestamp or restatement/version identity is documented. FiinQuantX fundamentals can therefore be integrated as period-aware structured data, but SHALL NOT be advertised as publication-aware or historical-as-of safe without an additional verified field or enrichment source.

### Financial ratios

```python
client.FundamentalAnalysis().get_ratios(
    tickers=tickers,
    years=[2024],
    quarters=[1, 2, 3, 4],
    type="consolidated",
    fields=["ProfitabilityRatio.ROA"],
)
```

Documented examples include gross margin, EBIT margin, net margin, ROA, ROE and ROIC. Available fields vary by subscription package; field availability is entitlement dependent.

### Vendor stock screener

```python
client.StockScreening().get(
    filter=[...],
    screenerDate="YYYY-MM-DD",
    exchanges=[...],
    sectors=[...],
)
```

The result has dynamic columns based on requested criteria. This is a namespaced vendor query capability, not a canonical substitute for raw reference or fundamental datasets.

## Verified streaming API inventory

### Tick stream

```python
stream = client.Trading_Data_Stream(tickers=tickers, callback=callback)
stream.start()
stream.stop()
```

The callback receives `RealTimeData`; `to_dataFrame()` exposes tick-level market fields.

### Historical plus realtime bars

```python
event = client.Fetch_Trading_Data(
    realtime=True,
    tickers=tickers,
    fields=[...],
    by="1m",
    callback=callback,
    wait_for_full_timeFrame=False,
)
event.get_data()
event.stop()
```

### Order-book stream

```python
stream = client.BidAsk(tickers=tickers, callback=callback)
stream.start()
stream.stop()
```

The documented order-book object includes up to ten price and volume levels, spread, depth imbalance and tick deltas.

The current `PluginRuntime.fetch()` and local REST service are synchronous and have no streaming/WebSocket contract. These APIs SHALL be deferred to a separate streaming architecture slice/change rather than implemented as a fake synchronous dataset.

## Explicitly excluded SDK areas

The documentation includes a complete section for:

```text
broker login
account information
loan/funding information
cash and buying power
order creation/update/cancel
order lists
positions
closing derivatives deals
```

These functions are outside the **read-only research boundary** and SHALL NOT be imported, registered, called, tested as provider capabilities or exposed by CLI, REST, TUI, MCP or assistant paths.

Data authentication through `FiinSession` is allowed. Broker/account/order classes and methods are not.

The implementation SHALL use an explicit SDK-member allowlist and architecture tests to prevent accidental access to the trading section.

## Documentation inconsistencies requiring live contract probes

The mirror is detailed but contains inconsistencies that prevent blind implementation:

1. Documentation version page says `0.1.60` is latest, while the official package index lists `0.1.64`.
2. Summary files and mirror files use different method names; mirror method names are authoritative for design.
3. `timestamp` is documented as both `str` and `int` across pages.
4. Returned field names mix PascalCase, camelCase and snake_case.
5. One hybrid-data page reverses the descriptions of `fb` and `fs`; historical-data and sample-schema pages describe `fb` as buy and `fs` as sell.
6. Some examples show helper calls returning a DataFrame directly while others append `.get_data()`.
7. `freefloat` unit is unclear.
8. Full-universe `reference.symbols`, historical constituent effective dates and direct outstanding-share history are not documented.
9. A synchronous `equity.quote` method is not documented; a realtime stream is not equivalent to a bounded quote fetch.
10. Entitlement, quota, session expiry and exact exception APIs are not documented.
11. Financial records do not document publication time or restatement identity.

These are required probe cases, not documentation cleanup details.

## Revised discovery consequence

Documentation discovery is substantially complete and enables implementation planning. Runtime implementation still requires a licensed, bounded probe against the approved SDK version to confirm:

```text
installed version and supported Python versions
exact return object types
actual columns and dtypes
empty/error behavior
credential/session expiry behavior
entitlement differences by account
rate, connection and quota limits
timestamp/timezone semantics
adjusted-price semantics
free-float units
fb/fs sign and direction
publication/restatement availability
license permissions for persistence and service exposure
```

Only capabilities with documented methods, approved normalizers, synthetic contract fixtures and licensed runtime verification may be enabled.