# Validation: FiinQuantX Data Provider Integration

## Status

```text
OpenSpec authored: yes
Detailed documentation inventory: complete
Licensed SDK runtime verification: partial; bounded OHLCV and membership verified
Commercial/license decision: runtime acknowledgement enforced; agreement review pending
Runtime implementation: four experimental, explicit-only datasets enabled
Offline runtime validation: passed for provider, contract and service slices
Licensed live validation: passed for bounded equity OHLCV and index membership
Strict OpenSpec validation after implementation: passed
Phase gates: G0A passed; G0B-G7 pending
```

## Runtime implementation evidence

Implementation commit: `0bd6a5d316bc9dea9eed7c3fda98209609a5bff7`.

| Check | Environment | Result | Safe evidence |
|---|---|---|---|
| base package remains optional | Python 3.11 Linux container | passed | `vnstock-service:base-check` imports `vnstock`; `FiinQuantX` is absent |
| approved package runtime | Python 3.11.15 Linux container | passed | distribution `fiinquantx==0.1.64`, import `FiinQuantX` |
| session and positive allowlist | same licensed container | passed | `FiinSession(...).login()`, `Fetch_Trading_Data`, and `TickerList` were exercised without exposing session material |
| bounded market data | same licensed container | passed | equity and index requests with `count_back=2` returned two canonical OHLCV rows each |
| membership snapshots | same licensed container | passed | index and sector requests returned canonical current-snapshot rows with observation timestamps |
| opt-in live tests | same licensed container | passed | `tests/live/providers/test_fiinquantx_live.py`: 2 passed |
| disabled company reference | local service | passed | explicit `source=FIINQUANTX` produced `422 unsupported_dataset_for_provider`; no fallback |
| forbidden auth route | local service | passed | `GET /v1/auth/login` produced 404 |

The enabled service datasets are `equity.ohlcv`, `index.ohlcv`,
`reference.index_membership_snapshot`, and
`reference.sector_membership_snapshot`. `reference.company_info` remains
disabled because the bounded `BasicInfor` probe did not establish a reliable
canonical contract. No raw licensed rows, credentials, session data, or auth
payloads were recorded.

Commands run against the implementation commit:

```text
cd vnstock
PYTHONPATH=. pytest -q tests/unit/providers/test_fiinquantx_foundation.py tests/unit/providers/test_fiinquantx_bridge.py tests/unit/service/test_service_contract.py tests/unit/service/test_runtime_integration.py
ruff check vnstock/providers/fiinquantx vnstock/core/contracts vnstock/service tests/unit/providers/test_fiinquantx_foundation.py tests/unit/providers/test_fiinquantx_bridge.py tests/unit/service/test_service_contract.py tests/unit/service/test_runtime_integration.py tests/live/providers/test_fiinquantx_live.py
ruff format --check (the same focused paths)
docker build --build-arg INSTALL_FIINQUANTX=false -t vnstock-service:base-check .
docker build --build-arg INSTALL_FIINQUANTX=true -t vnstock-service:latest .
VNSTOCK_LIVE_TESTS=true VNSTOCK_LIVE_PROVIDERS=FIINQUANTX pytest -q tests/live/providers/test_fiinquantx_live.py -m live
```

## Offline foundation evidence

Environment: OpenStock commit `64f0337`, Python 3.12.3 on Linux, with no
`fiinquantx` package and no licensed credentials configured.

```text
cd vnstock
PYTHONPATH=. pytest -q tests/unit/providers/test_fiinquantx_foundation.py tests/unit/providers/test_fiinquantx_bridge.py
```

Result: `passed` — 5 tests passed. The default registry constructs without the
SDK, the bridge reports `NOT_INSTALLED`, the provider exposes no enabled
capabilities, and explicit fetches fail closed.

Licensed probes, live provider tests, and the commercial agreement review are
`inconclusive`/`not run` in this environment. They must not be represented as
passing evidence or used to enable a capability.

No runtime capability, provider support or licensed behavior is claimed by this
offline-safe foundation.

## Evidence rules

- Record the exact OpenStock commit tested.
- Record the exact FiinQuantX SDK version tested.
- Record Python version and operating system.
- Distinguish documentation evidence from licensed runtime evidence.
- Do not attach credentials, session state or raw licensed production payloads.
- Synthetic fixtures must include a provenance statement confirming they contain no licensed values.
- Live-test output may include only safe method, shape, count, hash, duration and status metadata.
- Record `passed`, `failed`, `skipped`, `inconclusive` or `not run`; never infer a result.
- A documented method is not an enabled capability until runtime verification, canonical normalization and contract tests pass.
- A valid empty result is not proof of entitlement.
- No task may be checked from PR prose alone.

## Documentation review ledger

| Source | Revision | Result |
|---|---|---|
| `fiinquant/fiinquantx` public repository | `abb1e038f3e7401ab770067c5d7a539a06823097` | Binary wheel distribution repository reviewed. |
| Official package index | same revision | Latest indexed wheel observed: `fiinquantx-0.1.64-py3-none-any.whl`. |
| OpenStock FiinQuant docs mirror | commit `30b684d48911a3e0cf6e7c98fac6a2aa2b790f24`, PR #103 | 125-page detailed mirror reviewed as method/schema design source. |
| `docs/fiinquant/site/tai-lieu-ki-thuat/cai-dat-va-chuan-bi.md` | PR #103 | Official extra-index installation command recorded. |
| `docs/fiinquant/site/tai-lieu-ki-thuat/dang-nhap-tai-khoan.md` | PR #103 | `FiinSession(username, password).login()` recorded. |
| `TickerList` and `BasicInfor` pages | PR #103 | Current membership and company/ICB reference methods recorded. |
| Historical/realtime/order-book pages | PR #103 | Synchronous historical method and separate streaming methods recorded. |
| `PriceStatistics` pages | PR #103 | Market-cap, foreign, free-float, price-limit and investor-flow methods/fields recorded. |
| Fundamental and ratio pages | PR #103 | Period, scope, audit and nested company-type structures recorded; publication time absent. |
| Valuation and breadth pages | PR #103 | Separate stock/sector/index valuation and current breadth snapshot recorded. |
| Section 7 trading/account pages | PR #103 | Permanently excluded from provider scope. |

## G0A documentation findings

Verified documented calls:

```text
FiinSession(...).login()
TickerList(ticker=...)
BasicInfor(tickers=...).get()
Fetch_Trading_Data(realtime=False, ...).get_data()
PriceStatistics().get_overview(...)
PriceStatistics().get_foreign(...)
PriceStatistics().get_freefloat(...)
PriceStatistics().get_ceilingfloor(...)
PriceStatistics().get_value_by_investor(...)
MarketDepth().get_stock_valuation(...)
MarketDepth().get_sector_valuation(...)
MarketDepth().get_index_valuation(...)
MarketBreadth().get(...)
FundamentalAnalysis().get_financial_statement(...)
FundamentalAnalysis().get_ratios(...)
StockScreening().get(...)
MoneyFlow().get_contribution(...)
```

Documented streaming calls, explicitly deferred from synchronous `PluginRuntime.fetch()`:

```text
Trading_Data_Stream(...)
Fetch_Trading_Data(realtime=True, ...)
BidAsk(...)
OrderBook.track_order_book_changes(...)
```

Documented but permanently out-of-scope areas:

```text
broker/account login
account and loan information
cash/buying power
orders
positions
portfolio allocation
close derivatives deal
trading execution
```

## Required G0B licensed probe ledger

| Probe | OpenStock SHA | SDK version | Python/OS | Result | Safe evidence |
|---|---|---|---|---|---|
| package installation and metadata | pending | pending | pending | not run | pending |
| import and public allowlist | pending | pending | pending | not run | pending |
| login success/failure/session reuse | pending | pending | pending | not run | pending |
| entitlement/access behavior | pending | pending | pending | not run | pending |
| limit/quota/concurrency behavior | pending | pending | pending | not run | pending |
| historical bars return object and schema | pending | pending | pending | not run | pending |
| timestamp type/timezone | pending | pending | pending | not run | pending |
| adjusted/unadjusted price semantics | pending | pending | pending | not run | pending |
| `bu/sd/fb/fs/fn` units and direction | pending | pending | pending | not run | pending |
| PriceStatistics method schemas | pending | pending | pending | not run | pending |
| free-float unit | pending | pending | pending | not run | pending |
| membership/reference return shape | pending | pending | pending | not run | pending |
| breadth freshness/current-only behavior | pending | pending | pending | not run | pending |
| stock/sector/index valuation | pending | pending | pending | not run | pending |
| statement shapes by company type | pending | pending | pending | not run | pending |
| ratios by subscription entitlement | pending | pending | pending | not run | pending |
| publication/restatement metadata | pending | pending | pending | not run | pending |
| commercial persistence/exposure permission | pending | n/a | n/a | not run | pending |

## Required offline cases

### Provider foundation

```text
SDK absent
SDK present with approved version
SDK present with untested version
credentials missing
login failure
session invalidation
access/entitlement failure
valid empty dataset
rate/limit failure
unexpected provider failure
secret redaction
forbidden SDK member import/call
PluginRuntime-only execution path
explicit source no fallback
auto-source routing decision
```

### Documentation inconsistency regressions

```text
timestamp returned as string
timestamp returned as integer
PascalCase/camelCase/snake_case aliases
unknown field casing
fb=foreign buy and fs=foreign sell verified mapping
conflicting fb/fs fixture rejected
method returns DataFrame directly
method returns object requiring get_data()
freefloat unit unknown
freefloat unit verified
SDK version contract drift
```

### Dataset contracts

```text
equity and index OHLCV
adjusted and unadjusted OHLCV
current index membership snapshot
current sector membership snapshot
company/ICB reference
price limits
foreign flow
foreign ownership/room
investor flow dimensions
market-cap history by aggregation frequency
free-float history if unit verified
breadth snapshot
stock valuation
sector valuation and ICB level
index valuation
nested fundamentals by company type
financial-ratio field entitlement
publication time missing and historical_as_of_eligible=false
vendor analytics namespacing
```

### Boundary cases

```text
no synchronous equity.quote capability inferred from streaming docs
no historical membership dates invented
no full reference.symbols synthesized from partial index lists
no outstanding-share history advertised without verified method
no publication timestamp fabricated
no streaming call from ProviderPlugin.fetch()
no broker/account/order/position/allocation/execution import or route
```

## Expected focused commands

Paths may be adjusted only to actual implementation locations while preserving coverage:

```bash
cd vnstock

PYTHONPATH=. pytest -q \
  tests/unit/providers/fiinquantx \
  tests/contracts/providers/test_fiinquantx_contracts.py

PYTHONPATH=. pytest -q \
  tests/unit/core/provider \
  tests/unit/core/auth \
  tests/contracts/providers \
  tests/unit/service
```

## Required repository validation

```bash
cd vnstock
ruff check .
ruff format --check .
PYTHONPATH=. pytest -m "not slow" tests/unit/core tests/unit/ui tests/unified_ui tests/contracts
python -m build --sdist --wheel --no-isolation
cd ..
openspec validate fiinquantx-provider-integration --strict
```

Base-package packaging validation SHALL run without FiinQuantX installed.

## Licensed live validation

Live validation is opt-in and bounded:

```bash
cd vnstock
VNSTOCK_LIVE_TESTS=true \
VNSTOCK_LIVE_PROVIDERS=FIINQUANTX \
VNSTOCK_FIINQUANTX_LICENSED=true \
PYTHONPATH=. pytest -q tests/live/providers/test_fiinquantx_live.py -m live
```

Live test requirements:

- use a minimal approved ticker/date scope;
- do not print raw DataFrames or licensed rows;
- record safe package version, method, requested scope, columns, dtypes, row counts, data hashes, latency and result status;
- record whether data was persisted;
- cleanly stop any session resources;
- do not invoke streaming or trading/account APIs during synchronous provider validation.

## Cross-provider evidence

Bounded OHLCV comparisons against KBS/VCI SHALL record:

```text
common dates
coverage gaps
price-scale divergence
adjusted/unadjusted state
OHLC divergence
volume/value unit divergence
symbol/index mapping
holiday/empty behavior
```

Differences remain typed diagnostics. Tests must not mutate FiinQuantX values to match another provider silently.

## Packaging evidence

### Environment A — base package

Required:

- FiinQuantX not installed;
- import `vnstock` succeeds;
- default plugin registry succeeds;
- existing providers remain available;
- FiinQuantX reports safe unavailable state if represented by a placeholder plugin;
- build succeeds.

### Environment B — licensed package

Required:

- exact approved SDK version installed;
- safe auth/session status works;
- approved synchronous capabilities register;
- contract and bounded live tests pass;
- forbidden SDK methods remain inaccessible;
- no credentials or licensed rows are emitted.

## Phase-gate ledger

| Gate | Exact commit | Result | Evidence |
|---|---|---|---|
| G0A documentation inventory | OpenSpec branch after PR #103 review | passed | `source-review.md`, rewritten proposal/design/tasks/spec |
| G0B licensed runtime/commercial verification | pending | not run | pending |
| G1 optional provider foundation | pending | not run | pending |
| G2 reference and historical market | pending | not run | pending |
| G3 flow/ownership/market structure/valuation | pending | not run | pending |
| G4 period-aware fundamentals | pending | not run | pending |
| G5 namespaced vendor analytics | pending | not run | pending |
| G6 streaming architecture | pending | deferred to separate accepted change or not run |
| G7 full offline/package/live/OpenSpec | pending | not run | pending |
