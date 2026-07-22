# Design: FiinQuantX Data Provider Integration

## 1. Architectural position

FiinQuantX is an optional authenticated built-in provider inside the existing synchronous `vnstock` provider platform.

```text
Market / Reference / Fundamental public UI
or vnstock local read-only REST service
        ↓
PluginRuntime.fetch(dataset, params, return_result=True)
        ↓
PluginRouter
        ↓
PluginRegistry
        ↓
FiinQuantXProviderPlugin
        ↓
FiinQuantX SDK synchronous allowlisted method
        ↓
provider-specific raw-shape adapter
        ↓
versioned canonical normalizer
        ↓
DatasetContract + quality validation
        ↓
DataResult + safe diagnostics + lineage
```

The provider SHALL NOT introduce a second runtime, direct `vnalpha` integration or direct SDK calls from public UI/service code.

## 2. Existing platform constraints

The current platform already provides:

- runtime-checkable `ProviderPlugin`;
- instance-based `PluginRegistry`;
- auth- and health-aware `PluginRouter`;
- synchronous `PluginRuntime.fetch()`;
- `DataResult` metadata envelope;
- canonical dataset registry;
- dataset contract validation;
- provider drift and OHLCV comparison;
- local read-only REST endpoints.

The current runtime does not provide:

- async subscriptions;
- streaming callbacks;
- WebSocket lifecycle;
- provider-level rate limiting;
- persistent commercial quota tracking;
- first-class quality validators for reference/fundamental datasets.

The FiinQuantX design must extend these gaps explicitly rather than hiding them inside one adapter.

## 3. Target package layout

Use the established built-in provider namespace:

```text
vnstock/vnstock/providers/fiinquantx/
├── __init__.py
├── plugin.py
├── sdk.py
├── session.py
├── capabilities.py
├── exceptions.py
├── diagnostics.py
├── limits.py
├── method_allowlist.py
├── mappings.py
├── version.py
└── normalize/
    ├── __init__.py
    ├── bars.py
    ├── reference.py
    ├── statistics.py
    ├── flows.py
    ├── valuation.py
    └── fundamentals.py
```

Platform extensions where needed:

```text
vnstock/vnstock/core/provider/contracts.py or current contract registry module
vnstock/vnstock/core/provider/drift.py
vnstock/vnstock/core/provider/compare.py
vnstock/vnstock/core/auth/
vnstock/vnstock/core/router.py
vnstock/vnstock/core/runtime.py
```

Tests:

```text
vnstock/tests/unit/providers/fiinquantx/
vnstock/tests/contracts/providers/test_fiinquantx_*.py
vnstock/tests/live/providers/test_fiinquantx_live.py
vnstock/tests/fixtures/providers/fiinquantx/synthetic/
```

Documentation:

```text
vnstock/docs/providers/FIINQUANTX.md
vnstock/docs/PROVIDER_HARDENING.md
vnstock/docs/PLUGIN_ARCHITECTURE_STATUS.md
```

## 4. Evidence levels

Each proposed capability has one of four evidence states:

```text
DOCUMENTED
  official mirrored docs identify method, parameters and sample fields

RUNTIME_VERIFIED
  licensed bounded probe confirms method, return object, fields, types and behavior

IMPLEMENTED
  adapter, canonical contract and versioned normalizer exist

ENABLED
  synthetic contract tests and required live smoke tests pass for the approved SDK version
```

Only `ENABLED` capabilities return `supported: true` from the production capability declaration.

The capability matrix may expose safe evidence metadata:

```json
{
  "documented": true,
  "runtime_verified": true,
  "implemented": true,
  "enabled": true,
  "tested_sdk_versions": ["0.1.64"]
}
```

## 5. Documentation and version authority

### 5.1 Sources

Implementation uses:

```text
SDK distribution: fiinquant/fiinquantx package index
API design source: docs/fiinquant/site/ mirror in OpenStock
Runtime truth: bounded probes against licensed installed SDK
```

Top-level `docs/fiinquant/05-Functions-Part*.md` summaries SHALL NOT supply callable method names when they differ from the detailed mirror.

### 5.2 Version policy

The mirror labels version `0.1.60` as latest, while the package index lists `0.1.64`. Initial implementation SHALL:

1. choose one approved version, expected to be `0.1.64` unless the licensed environment proves otherwise;
2. record package version using package metadata;
3. maintain a compatibility table per method/normalizer;
4. fail closed on an untested incompatible version;
5. run contract probes before adding a newer compatible version.

Example:

```python
SUPPORTED_SDK_CONTRACTS = {
    "0.1.64": "fiinquantx-contract-v1",
}
```

Do not use a broad untested version range such as `>=0.1.64`.

### 5.3 Secure installation

The official docs use:

```bash
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

Automated or operator installation guidance SHALL additionally require:

- an exact approved version;
- an approved package source configuration;
- a captured wheel hash or equivalent integrity decision where operationally possible;
- no vendored wheel in the OpenStock repository/package;
- a warning against installing an unpinned package with a mixed primary index.

Base `vnstock` dependencies SHALL NOT include FiinQuantX as a mandatory package.

## 6. SDK bridge and positive allowlist

### 6.1 Lazy import

`vnstock` imports and default registry construction must work when FiinQuantX is absent.

```python
def load_fiinquantx_sdk() -> FiinQuantXModule:
    # lazy import and exact-version verification
    ...
```

Typed states:

```text
not_installed
installed_untested_version
installed_supported
credentials_missing
authentication_failed
authenticated
```

### 6.2 Allowed SDK surfaces

Initial synchronous allowlist:

```text
FiinSession
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

Later vendor-query allowlist after separate acceptance:

```text
StockScreening.get
MoneyFlow.get_contribution
```

Streaming methods are not in the synchronous provider allowlist:

```text
Trading_Data_Stream
Fetch_Trading_Data with realtime=True
BidAsk
OrderBook.track_order_book_changes
```

### 6.3 Permanently forbidden surfaces

Any SDK class or method whose purpose includes the following is forbidden:

```text
broker credential login
account data
cash/buying power
loan/funding packages
order creation/update/cancel
order lists
positions
portfolio execution
closing derivative deals
```

Provider code SHALL not import these members even if the installed SDK exposes them.

Add architecture tests that inspect provider imports/calls and fail on forbidden names. The test must use a maintained forbidden-member set, not free-form warning text.

## 7. Authentication and session lifecycle

### 7.1 Credential source

Documented session creation:

```python
client = FiinSession(username=username, password=password).login()
```

Credentials may be resolved from:

```text
FIINQUANT_USERNAME
FIINQUANT_PASSWORD
existing local credential/keyring abstraction
```

Credentials SHALL NOT be accepted through:

- provider data params;
- REST query/body;
- TUI slash command;
- MCP or assistant tool;
- notebook helper output;
- `DataResult` or DataFrame attrs.

### 7.2 Session adapter

```python
class FiinQuantXSessionProvider:
    def get_session(self) -> object: ...
    def invalidate(self) -> None: ...
    def status(self) -> SafeAuthStatus: ...
```

The adapter SHALL:

- create sessions lazily;
- serialize initial login where required;
- reuse a live session only according to verified behavior;
- invalidate on verified auth/session failures;
- never log session objects or auth responses;
- avoid automatic unlimited login retries.

### 7.3 Runtime verification required

Docs verify username/password login but do not verify:

- exception classes for every failure;
- token/cookie contents;
- session expiry duration;
- refresh behavior;
- logout/cleanup semantics;
- concurrent-session limits.

These remain FQ-0B probes.

## 8. Provider plugin contract

```python
class FiinQuantXProviderPlugin:
    name = "FIINQUANTX"

    def capabilities(self) -> dict[str, object]: ...
    def auth_spec(self, dataset: str) -> AuthSpec: ...
    def validate_params(self, dataset: str, params: dict[str, object]) -> None: ...
    def fetch(self, dataset: str, params: dict[str, object]) -> pandas.DataFrame: ...
    def diagnostics(self) -> dict[str, object]: ...
```

`fetch()` SHALL:

1. reject unsupported/unverified datasets;
2. validate canonical parameters before login/provider I/O;
3. verify SDK version;
4. acquire a safe session;
5. check configured/known entitlement state;
6. enforce provider limits;
7. invoke one allowlisted synchronous SDK method;
8. normalize through a versioned normalizer;
9. return the canonical DataFrame;
10. wrap provider errors into typed platform errors.

## 9. Entitlement model

The documentation shows field availability may vary by package, especially financial ratios, but does not document an entitlement-inspection API.

Use two layers:

```text
implemented capability
  adapter and canonical contract exist

runtime availability
  current account has demonstrated access or the request returns a typed access failure
```

If the SDK provides entitlement metadata, cache only safe entitlement identifiers. If no entitlement API exists, derive a short-lived capability observation from bounded probe results without treating a successful empty dataset as entitlement proof.

Explicit FiinQuantX requests with no entitlement must return a typed entitlement/access error, not `EMPTY` and not fallback data.

## 10. Error taxonomy

Provider-specific internal errors:

```text
FiinQuantXNotInstalledError
FiinQuantXVersionError
FiinQuantXCredentialsMissingError
FiinQuantXAuthenticationError
FiinQuantXAccessError
FiinQuantXRateLimitError
FiinQuantXQuotaError
FiinQuantXSchemaError
FiinQuantXInvalidResponseError
FiinQuantXProviderError
```

At the plugin boundary these wrap into existing platform exceptions with safe public messages.

Normal output and diagnostics may include:

```text
exception_type allowlist
provider state
correlation ID
SDK version
method identifier
retry count
latency
```

They must not include credentials, tokens, cookies, account identifiers, raw auth responses or licensed records.

## 11. Parameter and entity normalization

### 11.1 Symbols

Canonical inputs use uppercase identifiers. FiinQuantX docs show equities, indices, derivatives and covered warrants can share ticker parameters.

The adapter SHALL classify or constrain asset type by dataset:

```text
equity.ohlcv → equity symbols only
index.ohlcv → index identifiers only
reference.index_membership_snapshot → index identifiers only
```

Do not infer security type from string shape alone when a verified reference source is available.

### 11.2 Dates

Canonical API uses ISO dates/timestamps. The provider bridge may format strings required by the SDK.

Validate before provider I/O:

- start <= end;
- exactly one of canonical `period` or `start` where the selected SDK method requires it;
- bounded maximum date range according to policy;
- explicit market timezone handling;
- no silent invalid-date fallback.

### 11.3 Intervals

Documented SDK interval values:

```text
1m 5m 15m 30m 1h 2h 4h 1d
```

Canonical interval map:

```text
1m → 1m
5m → 5m
15m → 15m
30m → 30m
1H → 1h
2H → 2h
4H → 4h
1D → 1d
```

Unsupported canonical intervals fail before SDK invocation.

## 12. Dataset mapping

### 12.1 `equity.ohlcv` and `index.ohlcv`

SDK method:

```python
Fetch_Trading_Data(realtime=False, ...).get_data()
```

Canonical mapping:

| FiinQuantX | Canonical |
|---|---|
| `ticker` | `symbol` |
| `timestamp` | `time` or contract date/index |
| `open` | `open` |
| `high` | `high` |
| `low` | `low` |
| `close` | `close` |
| `volume` | `volume` |
| `value` | `value` where contract permits |

Contract metadata SHALL include:

```text
adjusted requested
adjustment_state verified/unknown
lasted requested
incomplete_bar policy
source interval
provider timezone
SDK version
```

`bu`, `sd`, `fb`, `fs`, `fn` SHALL not be silently added to canonical OHLCV. They feed separate optional contracts.

### 12.2 `reference.company_info`

SDK method:

```python
BasicInfor(tickers).get()
```

Canonical mapping shall preserve company name, short name, exchange, tax code and ICB hierarchy. Tax code is optional and must be treated as reference data, not a secret.

### 12.3 Membership snapshots

SDK method:

```python
TickerList(ticker=index_or_sector)
```

Contracts:

```text
reference.index_membership_snapshot
reference.sector_membership_snapshot
```

Required fields:

```text
entity_id
member_symbol
observed_at
provider
source_query
membership_type
```

Because the method returns only a list and no documented historical effective date:

- the result represents observation time, not historical constituent effective time;
- repeated observations may build an observed history, but must not be labeled official effective history;
- weights remain unavailable unless another verified method supplies them.

### 12.4 Market-cap history

SDK method:

```python
PriceStatistics().get_overview(...)
```

Contract:

```text
market.market_cap_history
```

Preserve aggregation frequency. Daily, weekly, monthly, quarterly and yearly rows are not interchangeable.

### 12.5 Foreign flow and ownership

SDK method:

```python
PriceStatistics().get_foreign(...)
```

Split into:

```text
foreign_flow.daily
foreign_ownership.daily
```

`foreign_flow.daily` contains buy/sell/net matched and deal values/volumes.

`foreign_ownership.daily` contains room, ownership and percentages.

Do not duplicate room/ownership fields into every flow record if the canonical model keeps them separately.

### 12.6 Free-float history

SDK method:

```python
PriceStatistics().get_freefloat(...)
```

Contract candidate:

```text
reference.free_float_history
```

Runtime probe SHALL classify `freefloat` as one of:

```text
shares
ratio
percentage
index coefficient
unknown
```

Capability remains disabled while unit is unknown.

### 12.7 Price limits

SDK method:

```python
PriceStatistics().get_ceilingfloor(...)
```

Contract:

```text
market.price_limits.daily
```

Required fields:

```text
symbol
date
floor_price
ceiling_price
currency/price scale
provider
```

### 12.8 Investor flow

SDK method:

```python
PriceStatistics().get_value_by_investor(...)
```

Contract:

```text
investor_flow.daily
```

Use dimensions instead of dozens of public columns where possible:

```text
symbol
date
investor_origin: domestic|foreign|proprietary
investor_type: individual|institutional|proprietary|unknown
venue: matched|deal|total
side: buy|sell
measure: volume|value|trade_count
value
unit
```

`openInterest` is derivative-specific and belongs in a derivative market contract, not an equity flow row.

### 12.9 Market breadth

SDK method:

```python
MarketBreadth().get(...)
```

Contract:

```text
market.breadth_snapshot
```

Required fields:

```text
index_code
observed_at or trading_date
advancers
decliners
unchanged
floor_count
ceiling_count
provider
```

No history is claimed from the documented method.

### 12.10 Valuation

Separate contracts:

```text
valuation.stock.daily
valuation.sector.daily
valuation.index.daily
```

Common fields:

```text
entity_id
entity_type
date
pe
pb
provider
methodology_status
```

Sector rows additionally preserve ICB level. Entity scopes SHALL never be mixed in one ambiguous ticker column.

### 12.11 Structured fundamentals

SDK method:

```python
FundamentalAnalysis().get_financial_statement(...)
```

The adapter must support company-type-specific nested schemas. Use a canonical line-item model or deterministic mapping layer that preserves raw vendor paths:

```text
symbol
fiscal_year
fiscal_quarter
period_type
statement_type
report_scope: consolidated|separate
audited
company_type
canonical_line_item
vendor_field_path
value
currency
unit
provider
```

The runtime probe must determine currency/unit behavior. Never infer VND scale from large integers alone.

Temporal fields:

```text
fiscal_period_end: derived only by an explicit deterministic calendar rule
publication_time_status: unknown unless source supplies a defensible timestamp
published_at: null unless verified
historical_as_of_eligible: false unless published_at/available_from is verified
```

This prevents FiinQuantX period data from creating historical lookahead.

### 12.12 Financial ratios

SDK method:

```python
FundamentalAnalysis().get_ratios(...)
```

Preserve:

```text
symbol
year
quarter
report_scope
ratio_group
ratio_code
value
unit
vendor_field_path
package_tier/availability status where safely known
provider
```

Vendor ratios are source data. OpenStock-derived ratios should remain separately identified.

## 13. Documentation inconsistency probe matrix

Mandatory live probes for the approved SDK version:

| Inconsistency | Required decision |
|---|---|
| Docs 0.1.60 vs wheel 0.1.64 | exact supported contract version |
| `timestamp` string vs integer | accepted input/output conversion and timezone |
| Pascal/camel/snake field names | versioned aliases and fail-closed unknowns |
| `fb`/`fs` reversed on one page | verified direction and sign |
| direct DataFrame vs `.get_data()` | exact return type per method |
| `freefloat` unclear | unit and scale |
| adjusted price unspecified | adjustment methodology/status |
| entitlement not documented | safe runtime access classification |
| no fundamentals publication time | explicit historical suitability status |

Synthetic fixtures SHALL include both expected and known-drift variants.

## 14. Rate, connection and quota controls

The current platform has cooldown but no provider rate limiter. FiinQuantX needs a provider-local limiter initially:

```python
@dataclass
class FiinQuantXLimitPolicy:
    max_concurrent_calls: int
    requests_per_second: float | None
    requests_per_minute: int | None
    request_timeout_seconds: float
    max_attempts: int
```

Limits may come from reviewed plan configuration when the SDK does not expose them. Unknown limits must use conservative bounded defaults; they must not be described as provider contract facts.

Do not retry:

```text
invalid parameters
credentials/authentication
access/entitlement
unsupported dataset
untested SDK version
schema incompatibility
hard quota exhaustion
```

Only verified transient network/provider failures may be retried with bounded jitter.

## 15. Diagnostics and lineage

Safe provider diagnostics:

```text
provider name
SDK installed yes/no
SDK version
contract version
credentials configured yes/no
authenticated state
last successful login/fetch timestamps
implemented datasets
observed access state by dataset
configured limit policy
health/cooldown
last safe error code
```

Successful `DataResult` metadata:

```text
provider=FIINQUANTX
dataset
sdk_version
contract_version
provider_method
fetched_at
request_window
source interval/frequency
adjustment state
quality status
contract validation summary
routing decision
```

Never attach the session, credentials, raw auth response or raw licensed payload.

## 16. Vendor analytics policy

`StockScreening`, `MoneyFlow.get_contribution`, technical indicators and other quantitative tools are not raw canonical datasets by default.

If enabled later they use namespaced contracts:

```text
screening.vendor
analytics.vendor_index_contribution
indicator.vendor_derived
```

Requirements:

- output labeled vendor-derived;
- dynamic fields described in metadata;
- input filters recorded;
- no silent substitution into OpenStock deterministic ranking/scoring;
- no allocation or execution semantics.

`Rebalance`, similar-chart prediction language and investment-strategy helpers are excluded from the initial provider integration.

## 17. Streaming architecture boundary

The documented streaming APIs require a separate design:

```text
Trading_Data_Stream
Fetch_Trading_Data(realtime=True)
BidAsk
```

A future streaming contract must define:

```text
SubscriptionRequest
StreamEvent
StreamStatus
subscription_id
sequence or provider ordering
received_at and event_time
reconnect/resubscribe
bounded queue/backpressure
callback failure isolation
session and market-status transitions
shutdown/stop guarantee
licensed persistence/retention
```

Until that exists:

- no streaming method is called by `ProviderPlugin.fetch()`;
- no REST WebSocket endpoint is added;
- no long-lived callback runs inside a synchronous request;
- no realtime stream is mislabeled as `equity.quote`.

## 18. Caching, persistence and commercial exposure

A license decision matrix is required for:

```text
in-process cache
SQLite cache
normalized local files
DuckDB/Postgres persistence
raw payload archive
local REST response
public or multi-user exposure
bulk export
research-derived features
model training
synthetic fixtures
```

Default before approval:

```text
raw archive: disabled
licensed rows in Git: forbidden
bulk export: disabled
public/multi-user service: disabled
live test persistence: disabled
synthetic fixtures: allowed after review
```

### 18.1 Local activation

The local deployment has no FiinQuantX approval boolean, reference or expiry
configuration. Bounded runtime use requires the exact SDK and local
credentials; warehouse persistence accepts the explicit source directly.

Credentials remain local-only. This access policy does not enable raw payload
archives, public or multi-user exposure, bulk export, model training,
streaming, or any broker/account/trading surface.

The provider, vnalpha source policy, Compose deployment, installed-host
verifier, tests, documentation, and OpenSpec artifacts SHALL NOT read, require,
emit, fingerprint, or persist approval configuration.

Safe runtime and warehouse lineage may record the provider, SDK/contract
version, source method, price basis, correlation, and ingestion run. It SHALL
NOT contain an approval value or fingerprint.
Gate A otherwise remains unchanged: all four datasets, PluginRuntime-only
routing, raw-unadjusted basis, explicit-source no-fallback behavior, bounded
licensed probes, canonical persistence, and clean-host E2E acceptance are still
required.

## 19. Routing behavior

### Explicit source

```text
source=FIINQUANTX
```

No silent fallback. Return a typed installation, version, credentials, auth, access, limit, schema, empty or provider failure.

### Auto source

`source=auto` considers:

- enabled canonical capability;
- authentication/access state;
- health and cooldown;
- commercial priority;
- quota/limit budget;
- freshness and adjustment requirement;
- deployment/license policy.

Existing providers remain available and unchanged.

## 20. Testing strategy

### Documentation contract tests

Static tests verify the implemented method/field mappings match the reviewed documentation inventory in `source-review.md`.

### Offline synthetic tests

Cover:

```text
SDK absent
unsupported SDK version
credentials missing
authentication failure
access failure
valid and empty returns
return object variation
field naming variation
timestamp string/integer
fb/fs direction mapping
freefloat unit unknown/verified
adjusted/unadjusted OHLCV
schema drift
nested statement variants by company type
ratio entitlement differences
missing publication timestamp
forbidden SDK member boundary
secret redaction
PluginRuntime-only path
```

### Licensed live tests

Disabled by default:

```bash
VNSTOCK_LIVE_TESTS=true \
VNSTOCK_LIVE_PROVIDERS=FIINQUANTX \
PYTHONPATH=. pytest -q tests/live/providers/test_fiinquantx_live.py -m live
```

Tests use minimal symbols/date ranges and log only safe shape/count/hash metadata.

### Cross-provider comparison

Compare bounded FiinQuantX OHLCV against KBS/VCI for:

- common dates;
- price scale;
- adjustment state;
- OHLC divergence;
- volume/value units;
- symbol/index mapping;
- empty/holiday behavior.

No silent reconciliation.

## 21. Backward compatibility

- Base package imports without FiinQuantX.
- Default registry construction succeeds without SDK.
- Existing provider names and explicit source behavior remain valid.
- No current default routing changes unless separately configured.
- Existing synchronous service endpoints remain synchronous.
- No legacy provider is removed.

## 22. Read-only boundary

The integration is limited to licensed market/reference/fundamental data retrieval and deterministic normalization.

It SHALL NOT add or expose:

```text
broker login
account data
cash/buying power
loan/margin data
orders
positions
portfolio allocation
transfer
trade execution
automated trading
```

The **read-only research boundary** applies even when the commercial SDK offers those functions.
