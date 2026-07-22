# fiinquantx-provider-integration Specification Delta

## ADDED Requirements

### Requirement: FiinQuantX shall be an optional exact-version provider

The system SHALL integrate FiinQuantX as an optional authenticated provider. Base `vnstock` import, registry construction, tests, package build and existing providers SHALL remain functional when FiinQuantX is not installed.

The initial implementation SHALL support only explicitly approved SDK contract versions and SHALL NOT assume that a newer wheel is compatible solely because it has a higher version number.

#### Scenario: Base package runs without FiinQuantX

- **WHEN** the normal `vnstock` package is installed without FiinQuantX
- **THEN** importing `vnstock` succeeds
- **AND** the default plugin registry can be constructed
- **AND** existing providers remain available
- **AND** FiinQuantX reports a safe not-installed or unavailable state rather than breaking imports

#### Scenario: Untested FiinQuantX version is installed

- **WHEN** FiinQuantX is installed
- **BUT** its version is not mapped to an accepted contract version
- **THEN** the provider fails closed with a typed compatibility error
- **AND** does not invoke SDK data methods
- **AND** identifies the installed version safely in diagnostics

#### Scenario: Approved version is installed

- **WHEN** a supported exact FiinQuantX version is installed
- **AND** the corresponding normalizer and contract tests pass
- **THEN** the provider may expose the capabilities enabled for that contract version
- **AND** no FiinQuantX wheel or proprietary source is embedded into the OpenStock package

### Requirement: Secure installation shall be documented and bounded

The system SHALL document the official FiinQuantX package source while requiring a supported exact version and an integrity decision. It SHALL NOT require an unpinned commercial package from a mixed package index as part of the base dependency set.

#### Scenario: Operator installs FiinQuantX

- **WHEN** an operator prepares a licensed FiinQuantX environment
- **THEN** installation guidance specifies the approved exact version
- **AND** uses the reviewed official package source
- **AND** records a wheel hash or equivalent package-integrity decision where feasible
- **AND** warns against unpinned mixed-index installation

### Requirement: Documentation evidence and runtime evidence shall remain distinct

The system SHALL treat the committed detailed documentation mirror as method/schema design evidence and a licensed bounded probe as runtime evidence.

#### Scenario: Method appears in detailed documentation

- **WHEN** a method, parameter or field is documented under `docs/fiinquant/site/`
- **THEN** it may be included in the implementation design
- **BUT** the capability remains disabled until the licensed SDK return type, schema, units and failure behavior are verified

#### Scenario: Summary guide disagrees with detailed mirror

- **WHEN** a top-level summary guide uses a method name different from the detailed mirror
- **THEN** the detailed mirror governs the design inventory
- **AND** the licensed SDK probe determines the runtime contract
- **AND** the system does not implement the inferred summary method name without verification

### Requirement: The provider shall use a positive SDK data-method allowlist

The provider SHALL invoke only reviewed data-retrieval methods. Broker, account, financing, order, position, allocation, transfer, margin and execution methods SHALL be forbidden even when exposed by the installed SDK.

Initial synchronous data-method candidates are:

```text
TickerList
BasicInfor
Fetch_Trading_Data with realtime=False
PriceStatistics.get_overview
PriceStatistics.get_foreign
PriceStatistics.get_freefloat
PriceStatistics.get_ceilingfloor
PriceStatistics.get_value_by_investor
MarketDepth.get_stock_valuation
MarketDepth.get_sector_valuation
MarketDepth.get_index_valuation
MarketBreadth.get
FundamentalAnalysis.get_financial_statement
FundamentalAnalysis.get_ratios
```

#### Scenario: Approved data method is called

- **WHEN** an enabled canonical dataset is fetched
- **THEN** the adapter invokes only the allowlisted SDK method mapped to that dataset
- **AND** records the safe method identifier in lineage

#### Scenario: Trading/account SDK member is referenced

- **WHEN** provider code imports or calls a forbidden broker, account, loan, buying-power, order, position, portfolio, transfer, margin or execution member
- **THEN** architecture and boundary tests fail
- **AND** the member cannot be registered as a provider capability

### Requirement: Authentication shall use FiinSession through local credential abstractions

The provider SHALL use the documented `FiinSession(username, password).login()` model through approved local credential/session abstractions.

Credentials SHALL NOT appear in provider data parameters, REST requests, TUI commands, MCP tools, assistant tools, notebooks, `DataResult`, DataFrame attributes, logs, diagnostics or exceptions.

#### Scenario: Valid local credentials are available

- **WHEN** approved local credential sources provide the FiinQuant username and password
- **THEN** the provider creates or reuses a session lazily
- **AND** exposes only a safe authenticated-state result
- **AND** passes no raw credentials through dataset requests

#### Scenario: Credentials are missing

- **WHEN** an explicit FiinQuantX request is made without configured credentials
- **THEN** the provider returns a typed credentials-missing error
- **AND** performs no provider data call
- **AND** does not fall back silently to another provider

#### Scenario: Authentication fails

- **WHEN** the SDK rejects login or an existing session
- **THEN** the provider invalidates the unsafe session state
- **AND** returns a typed sanitized authentication error
- **AND** does not expose username, password, token, cookie, account identifier or raw auth response

#### Scenario: REST login is requested

- **WHEN** a caller requests a FiinQuantX login/logout or raw-secret REST route
- **THEN** no such route is exposed
- **AND** credential management remains local and outside the read-only data service

### Requirement: Every synchronous FiinQuantX fetch shall use PluginRuntime

Every public UI and service-layer synchronous FiinQuantX fetch SHALL route through `PluginRuntime`, `PluginRouter` and `PluginRegistry`.

#### Scenario: Explicit canonical request uses FiinQuantX

- **WHEN** a canonical data request specifies `source=FIINQUANTX`
- **THEN** `PluginRuntime` applies parameter validation, provider routing, auth/access checks, health/cooldown, diagnostics and contract validation
- **AND** no public or service path calls the SDK directly

#### Scenario: Runtime bypass is introduced

- **WHEN** a public UI or local service implementation calls an FiinQuantX SDK data method directly
- **THEN** architecture regression tests fail

### Requirement: Explicit source selection shall never silently fall back

Explicit `source=FIINQUANTX` SHALL either return a valid FiinQuantX result or a typed FiinQuantX failure.

#### Scenario: Explicit FiinQuantX request cannot run

- **WHEN** the SDK is absent, version incompatible, credentials missing, authentication failed, access denied, limit exhausted, schema incompatible or provider execution failed
- **THEN** the request returns the corresponding typed sanitized outcome
- **AND** does not return KBS, VCI, DNSE, TCBS, MSN, FMP, FMARKET or another provider result

#### Scenario: Auto routing may fall back

- **WHEN** the caller requests `source=auto`
- **AND** policy permits fallback
- **THEN** the router may choose another implemented provider
- **AND** records why FiinQuantX was selected, rejected or bypassed

### Requirement: Provider access and limit state shall be bounded

The system SHALL distinguish implemented adapter support from current account access. It SHALL enforce verified or conservatively configured request/concurrency limits and bounded retry behavior.

#### Scenario: Dataset adapter exists but account lacks access

- **WHEN** an adapter and canonical contract exist
- **BUT** the licensed account rejects access to the dataset or fields
- **THEN** explicit FiinQuantX selection returns a typed access error
- **AND** does not represent the result as a valid empty dataset

#### Scenario: Retryable transient failure occurs

- **WHEN** a verified transient provider or network failure occurs
- **THEN** the adapter applies bounded retries with configured backoff/jitter
- **AND** respects provider concurrency and request limits
- **AND** records safe attempt metadata

#### Scenario: Non-retryable failure occurs

- **WHEN** failure is due to invalid input, credentials, authentication, access, unsupported dataset, untested version, incompatible schema or hard quota exhaustion
- **THEN** the provider does not retry

### Requirement: Parameters shall fail before session or provider I/O

The provider SHALL validate canonical symbols, asset type, dates, intervals, period/start exclusivity and bounded request windows before creating a provider session or invoking a data method.

#### Scenario: Invalid date window is supplied

- **WHEN** start date is later than end date or a date is malformed
- **THEN** the request fails with a typed validation error
- **AND** no login or SDK data call occurs

#### Scenario: Unsupported interval is supplied

- **WHEN** a canonical interval cannot map to the documented/verified FiinQuantX interval set
- **THEN** validation fails before provider I/O
- **AND** does not silently substitute another interval

#### Scenario: Period and start date conflict

- **WHEN** a historical-bars request supplies mutually exclusive period and start-date modes
- **THEN** validation fails before provider I/O

### Requirement: FiinQuantX field inconsistencies shall be normalized by versioned contracts

Provider-specific field casing, timestamp representation, return-object variation and documented naming inconsistencies SHALL remain inside versioned FiinQuantX normalizers.

#### Scenario: Timestamp is returned as a documented variant

- **WHEN** the approved SDK returns timestamp as a verified string or integer form
- **THEN** the versioned normalizer converts it to the canonical market time/date and timezone contract
- **AND** records the source representation in diagnostics where useful

#### Scenario: Unknown timestamp or field shape appears

- **WHEN** timestamp, field casing, return object or required columns do not match an approved contract variant
- **THEN** the adapter returns a typed schema/invalid-response failure
- **AND** does not guess or fabricate canonical values

#### Scenario: `fb` and `fs` direction is ambiguous

- **WHEN** runtime verification does not establish foreign-buy and foreign-sell direction/sign
- **THEN** the related flow capability remains disabled
- **AND** OHLCV may still proceed without those optional flow fields

### Requirement: Historical bars shall preserve adjustment and incomplete-bar semantics

`equity.ohlcv` and `index.ohlcv` SHALL use the verified synchronous `Fetch_Trading_Data(realtime=False)` contract and preserve adjustment, interval and incomplete-bar state.

#### Scenario: Historical OHLCV is requested

- **WHEN** valid equity or index parameters are supplied
- **THEN** the adapter maps ticker, timestamp, OHLC, volume and optional value to the canonical contract
- **AND** records requested/verified adjustment state
- **AND** records whether incomplete latest bars were requested or excluded
- **AND** runs contract validation

#### Scenario: Flow fields accompany historical bars

- **WHEN** the SDK returns `bu`, `sd`, `fb`, `fs` or `fn`
- **THEN** canonical OHLCV does not silently add those fields as unrelated columns
- **AND** flow values enter only an approved flow contract

#### Scenario: Synchronous quote capability is requested

- **WHEN** no bounded synchronous quote method has been verified
- **THEN** FiinQuantX does not advertise `equity.quote`
- **AND** realtime streaming documentation is not treated as proof of synchronous quote support

### Requirement: Company and membership reference shall preserve snapshot semantics

The provider SHALL expose documented company/ICB reference and current membership as snapshot data.

#### Scenario: Company reference is requested

- **WHEN** `reference.company_info` is fetched
- **THEN** `BasicInfor(...).get()` is mapped to canonical company name, short name, exchange, tax code and ICB hierarchy
- **AND** unknown optional fields remain null rather than fabricated

#### Scenario: Index membership is requested

- **WHEN** a documented index identifier is supplied to `TickerList`
- **THEN** the provider returns `reference.index_membership_snapshot`
- **AND** records observation time and source query
- **AND** does not claim an historical effective date or weight that the method did not supply

#### Scenario: Sector membership is requested

- **WHEN** a documented sector alias or ICB code is supplied to `TickerList`
- **THEN** the provider returns `reference.sector_membership_snapshot`
- **AND** preserves the sector alias/code and observation time

#### Scenario: Full symbol universe is requested

- **WHEN** a complete current universe and asset classification method has not been verified
- **THEN** FiinQuantX does not advertise `reference.symbols`
- **AND** does not synthesize the universe from a few index lists

### Requirement: Price and market-statistics contracts shall remain explicit

The provider SHALL use separate contracts for market-cap history, price limits, breadth snapshots and free-float history.

#### Scenario: Market-cap series is fetched

- **WHEN** `PriceStatistics.get_overview()` succeeds
- **THEN** `market.market_cap_history` preserves symbol/entity, frequency, period/date, market cap, trading statistics and units
- **AND** Daily/Weekly/Monthly/Quarterly/Yearly rows are not mixed without frequency metadata

#### Scenario: Daily price limits are fetched

- **WHEN** `get_ceilingfloor()` succeeds
- **THEN** `market.price_limits.daily` preserves symbol, date, floor, ceiling and verified price scale

#### Scenario: Breadth is fetched

- **WHEN** `MarketBreadth.get()` succeeds
- **THEN** `market.breadth_snapshot` preserves index code, trading/observation date, advancers, decliners, unchanged, floor and ceiling counts
- **AND** does not advertise historical breadth because the documented method has no historical parameters

#### Scenario: Free-float unit is unresolved

- **WHEN** the SDK returns `freefloat`
- **BUT** runtime verification cannot determine whether it represents shares, ratio, percentage or coefficient
- **THEN** `reference.free_float_history` remains disabled
- **AND** no canonical unit is invented

### Requirement: Foreign flow and ownership shall be separate contracts

The system SHALL distinguish foreign trading flow from foreign ownership/room state.

#### Scenario: Foreign daily data is fetched

- **WHEN** `PriceStatistics.get_foreign()` returns verified data
- **THEN** buy/sell/net matched, deal and total volume/value map to `foreign_flow.daily`
- **AND** current/total room and owned/percentage fields map to `foreign_ownership.daily`
- **AND** sign, unit and aggregation frequency are explicit

#### Scenario: Flow direction cannot be verified

- **WHEN** foreign buy/sell direction or net sign cannot be verified for the installed SDK version
- **THEN** flow capability fails closed or remains disabled
- **AND** room/ownership capability may proceed independently if its contract is verified

### Requirement: Investor-classified flow shall use a dimensional contract

The system SHALL normalize domestic individual, domestic institutional, foreign individual, foreign institutional and proprietary flow into a dimensional `investor_flow.daily` contract rather than expose a fragile list of provider-specific columns.

#### Scenario: Investor flow is fetched

- **WHEN** `PriceStatistics.get_value_by_investor()` succeeds
- **THEN** each normalized measure identifies symbol, date, investor origin/type, matched/deal/total venue, buy/sell side, volume/value/trade-count measure, value and unit
- **AND** source field lineage remains available

#### Scenario: Derivative open interest appears

- **WHEN** the response includes derivative `openInterest`
- **THEN** it is excluded from equity investor-flow rows
- **AND** is exposed only through an approved derivative contract

### Requirement: Valuation contracts shall be separated by entity scope

Stock, sector and index valuation SHALL use separate contracts.

#### Scenario: Stock valuation is fetched

- **WHEN** `get_stock_valuation()` succeeds
- **THEN** the provider returns `valuation.stock.daily` with stock identifier, date, P/E and P/B

#### Scenario: Sector valuation is fetched

- **WHEN** `get_sector_valuation()` succeeds
- **THEN** the provider returns `valuation.sector.daily`
- **AND** preserves ICB level and sector identifier

#### Scenario: Index valuation is fetched

- **WHEN** `get_index_valuation()` succeeds
- **THEN** the provider returns `valuation.index.daily`
- **AND** does not mix index identifiers with stock identifiers under one ambiguous contract

### Requirement: FiinQuantX fundamentals shall be period-aware and publication-time honest

The provider SHALL normalize documented structured statements and ratios by fiscal period, statement scope, audit state and company type. It SHALL NOT advertise FiinQuantX-only records as publication-aware or historical-as-of eligible unless a defensible publication/available-from timestamp is verified.

#### Scenario: Financial statement is fetched

- **WHEN** `FundamentalAnalysis.get_financial_statement()` returns a documented company-type-specific nested structure
- **THEN** the adapter preserves symbol, fiscal year, quarter/annual period, statement type, consolidated/separate scope, audited flag, company type, canonical line item, vendor field path, value and verified unit/currency
- **AND** handles manufacturing, securities, banking and insurance shapes through explicit mappings

#### Scenario: Financial ratios are fetched

- **WHEN** `FundamentalAnalysis.get_ratios()` returns accessible ratio fields
- **THEN** the provider preserves ratio group, ratio code, period, scope, value, unit and vendor field path
- **AND** represents package-tier missing fields as access/availability state rather than zero

#### Scenario: Publication time is absent

- **WHEN** a statement has year/quarter metadata but no defensible publication or available-from timestamp
- **THEN** normalized metadata sets publication time unknown
- **AND** marks the record `historical_as_of_eligible=false`
- **AND** does not substitute fiscal-period end as publication time
- **AND** downstream publication-aware analysis cannot silently use it

#### Scenario: Restatement identity is absent

- **WHEN** the SDK does not expose original/restated version identity
- **THEN** the provider discloses that historical revisions cannot be reconstructed from FiinQuantX alone
- **AND** does not claim restatement-safe history

### Requirement: Vendor analytics shall remain namespaced and non-authoritative

Stock screening, index contribution and vendor-calculated indicators SHALL remain distinguishable from canonical raw datasets and OpenStock deterministic logic.

#### Scenario: Vendor screener is enabled

- **WHEN** `StockScreening.get()` is implemented
- **THEN** it returns a namespaced `screening.vendor` result
- **AND** records filter, screen date, exchange/sector constraints and dynamic field definitions
- **AND** does not become a hidden substitute for canonical raw data

#### Scenario: Vendor indicator is enabled

- **WHEN** a FiinQuantX indicator is exposed
- **THEN** it is labeled `indicator.vendor_derived`
- **AND** preserves vendor method/code, parameters, date/period, value/unit and provider version
- **AND** does not silently replace an OpenStock feature or score formula

#### Scenario: Allocation-oriented helper is encountered

- **WHEN** an SDK helper calculates shares to buy, portfolio rebalance or execution quantities
- **THEN** it is excluded from provider capabilities
- **AND** remains outside the **read-only research boundary**

### Requirement: Streaming APIs shall require a separate accepted architecture

The synchronous provider SHALL NOT call `Trading_Data_Stream`, realtime `Fetch_Trading_Data`, `BidAsk` or order-book-change subscriptions.

#### Scenario: Streaming capability is proposed

- **WHEN** realtime callback or order-book subscription support is requested
- **THEN** a separate OpenSpec defines subscription lifecycle, event envelope, ordering, reconnect, backpressure, shutdown, session and licensed-retention behavior
- **AND** synchronous `ProviderPlugin.fetch()` remains free of long-lived callbacks

#### Scenario: Stream is presented as quote fetch

- **WHEN** implementation attempts to label a realtime stream as synchronous `equity.quote`
- **THEN** capability and architecture tests fail

### Requirement: Commercial persistence and exposure shall require an approved decision

The provider SHALL enforce a reviewed commercial-policy decision for caching, persistence, raw archive, export, local service response, multi-user exposure and derived analytics.

#### Scenario: Permission is unknown

- **WHEN** permission for raw archive, normalized persistence, bulk export or multi-user exposure is not confirmed
- **THEN** the corresponding behavior remains disabled
- **AND** package availability is not treated as redistribution permission

#### Scenario: Synthetic fixture is committed

- **WHEN** a FiinQuantX test fixture is added to Git
- **THEN** it contains synthetic values only
- **AND** reproduces only the reviewed shape needed for tests
- **AND** contains no credential, account, customer or licensed production row

#### Scenario: Local REST exposure is permitted

- **WHEN** commercial policy permits canonical local REST output
- **THEN** exposure remains read-only and local according to service policy
- **AND** uses canonical contracts and safe metadata
- **AND** adds no credential, broker, account, order, position, portfolio, transfer, margin or trading endpoint

### Requirement: Provider outcomes shall remain typed and sanitized

The provider SHALL distinguish validation, not-installed, version, credentials, authentication, access, rate-limit, quota, schema, invalid-response, valid-empty and provider-runtime outcomes.

#### Scenario: Valid empty data is returned

- **WHEN** an allowlisted SDK method successfully returns no rows for a valid symbol/date/market condition
- **THEN** the platform represents a valid empty dataset according to the canonical contract
- **AND** does not misclassify it as credentials, access or provider failure

#### Scenario: Unexpected SDK exception occurs

- **WHEN** an unexpected SDK exception crosses the bridge boundary
- **THEN** it is wrapped into a typed platform provider error
- **AND** only safe exception type, correlation and provider-state metadata are recorded
- **AND** raw auth/provider payloads remain hidden

### Requirement: Existing providers and APIs shall remain backward compatible

Adding FiinQuantX SHALL NOT remove or change established providers and defaults unless a separate reviewed routing-policy change does so.

#### Scenario: FiinQuantX is unavailable

- **WHEN** a user runs existing KBS, VCI, DNSE, TCBS, MSN, FMP or FMARKET workflows without FiinQuantX
- **THEN** existing public APIs and explicit-source behavior remain unchanged

#### Scenario: Commercial priority is configured

- **WHEN** an operator configures FiinQuantX as preferred for a dataset family
- **THEN** auto routing applies that priority only after capability, auth/access, health, cooldown, limits, freshness, adjustment and commercial-policy checks
- **AND** records the selection reason

### Requirement: Live tests shall be licensed, bounded and opt-in

Normal CI SHALL not call FiinQuantX live services. Live tests SHALL require
explicit opt-in and minimal requests.

#### Scenario: Default CI runs

- **WHEN** offline CI executes
- **THEN** no FiinQuantX live method is called
- **AND** tests use synthetic fixtures
- **AND** no commercial credentials are required

#### Scenario: Licensed live test runs

- **WHEN** live-test, provider and licensed-environment flags are explicitly enabled
- **THEN** the test uses minimal approved symbols/date ranges
- **AND** logs only SDK version, method, scope, schema, row count, hashes, latency and safe statuses
- **AND** does not print raw licensed rows or credentials
- **AND** does not invoke streaming or forbidden trading/account methods during synchronous validation

### Requirement: FiinQuantX integration shall preserve the read-only research boundary

The system SHALL use FiinQuantX only for market, reference, flow, valuation, fundamental and approved vendor-derived research data.

#### Scenario: Disallowed financial action is requested

- **WHEN** a request requires broker login, account access, cash/buying power, loan/margin data, order placement/update/cancel, position management, portfolio allocation, transfer or execution
- **THEN** no FiinQuantX provider capability is available for that action
- **AND** no SDK trading/account member is called
- **AND** the **read-only research boundary** remains intact.
