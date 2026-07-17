# Validation: FiinQuantX Data Provider Integration

## Status

```text
OpenSpec authored: yes
Detailed documentation inventory: complete
Licensed SDK runtime verification: Gate A live evidence passed for the current remediation
Commercial/license decision: runtime acknowledgement enforced; agreement review pending
Runtime implementation: four experimental, explicit-only datasets enabled
Offline runtime validation: passed for raw-request, safe-lineage, membership-persistence, contract and service slices
Licensed live validation: current bounded Gate A provider, persistence and localhost smoke passed
Strict OpenSpec validation after implementation: passed
Phase gates: G0A and the implemented Gate A subset passed; full G0B and G3-G7 remain pending
```

## Current Gate A acceptance evidence (2026-07-17)

Environment: local Linux host; Python 3.11 service container bound only to
`127.0.0.1:6900`; FiinQuantX `0.1.64`; existing credentials supplied at
runtime without recording their values. The exact implementation commit is the
PR head containing this ledger; required CI and merge-SHA evidence remain PR
checks rather than being inferred here.

The approved policy for this acceptance is boolean-only acknowledgement:
`VNSTOCK_FIINQUANTX_LICENSED=true` and
`VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=true`. Both retired
approval-reference environment inputs, their values and fingerprints are
absent. All other provider, persistence and fail-closed gates remain enforced.

| Check | Result | Safe evidence |
|---|---|---|
| localhost service deployment | passed | health passed after build and again after restart; host publish is loopback-only |
| base image without proprietary SDK | passed | `vnstock` imports; FiinQuantX distribution is absent; five documented capabilities are unsupported |
| licensed image/runtime | passed | exact distribution `fiinquantx==0.1.64`; four implemented capabilities available only with SDK, credentials and boolean acknowledgement |
| equity and index OHLCV | passed | bounded FPT and VNINDEX requests returned two canonical rows each with `FIINQUANTX`, `RAW_UNADJUSTED`, `PASS` and `plugin_runtime` lineage |
| index and sector membership | passed | VN30 returned 30 canonical members and `BANKS_L2` returned 28; the SDK iterable wrapper is normalized without retaining vendor objects |
| stable reference universe | passed | strict VCI symbol reference returned and persisted 1,745 STOCK symbols with exchange; Fiin company reference remained disabled |
| explicit-source no fallback | passed | unsupported Fiin company-info request returned typed HTTP 422 and did not route to VCI |
| clean persistence and canonical build | passed | fresh warehouse persisted FPT and VNINDEX raw-unadjusted rows, built canonical rows and retained safe provider/basis/quality lineage; retired reference/fingerprint diagnostics were absent |
| assistant route and natural-language acceptance | passed | ya-router `thiendu` on `127.0.0.1:7071` passed structured preflight; a real Vietnamese FPT analysis completed with groundedness/policy PASS, correlated evidence and no licensed-row disclosure |
| reuse and deterministic degraded mode | passed | follow-up NL and `/analyze` reused persisted data without new ingestion; unavailable LLM route failed preflight while deterministic analysis remained available |
| restart durability | passed | service restart preserved warehouse, audit and validated-memory state; bounded Fiin and strict VCI probes passed again |
| offline regression and style | passed | vnstock: 1,384 passed, 1 skipped, 145 deselected using `not live and not integration`; Ruff check and format passed across 367 files |

No credentials, session material, model prose or raw licensed rows are stored
in this ledger. Counts, statuses, schema names and hashes are the only live
payload evidence retained. The full G0B probe matrix (including quotas and
disabled Gate B/C datasets) is not implied by this bounded Gate A acceptance.

## Earlier remediation evidence (2026-07-16)

That earlier offline environment had no FiinQuantX distribution, licensed credentials,
runtime approval, persistence approval, or commercial decision. The following
results are offline evidence only:

- exact SDK call tests verify bounded OHLCV requests set `adjusted=False` and
  `lasted=False`, and publish `basis=RAW_UNADJUSTED`;
- PluginRuntime tests verify allowlisted SDK/contract/source-method/snapshot
  lineage and exclude credential-like attrs;
- vnalpha tests verify source approval before run creation, typed membership
  endpoints, atomic current-snapshot/member persistence, valid `EMPTY`,
  fail-closed entity validation, CLI status, and boolean-only approvals;
- raw and canonical warehouse rows carry an explicit price basis; legacy
  FiinQuantX rows without verified basis, adjusted rows, and upstream quality
  failures are quarantined instead of colliding with raw-unadjusted evidence;
- research evidence and grounded answers disclose raw-unadjusted basis and
  overlapping corporate-action ranges rather than implying adjusted history;
- the installed-host verifier fails closed when either approval boolean, the
  separately approved reference provider, or any Gate A capability is absent;
- base-package tests continue to run without the proprietary SDK.

At that earlier checkpoint, live equity/index bars, timestamp/timezone/price/volume/value semantics,
incomplete-bar behavior, valid-empty behavior, membership semantics, exact SDK
installation, entitlement, quotas, commercial permission, and a fresh-host
smoke are `not run` for this remediation. Historical live evidence below does
not certify the changed `adjusted=False` request or the new vnalpha membership
persistence path.

## Historical runtime implementation evidence

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

## Review remediation evidence

The final runtime contract is implemented by commits
`18da95fcc00b1ea8be4630aaf6d51832da0953ec`,
`73b781e36f60651e9ed274dafa1311854afc2352`, and
`d0e801a48f910cf4ee6675239b08cbd933d8e6e1`.

- Credential-like query keys are rejected before runtime fetch, and access
  logging records no request target or query values.
- Capabilities require SDK, runtime acknowledgement, and both credential
  environment variables.
- `explicit_only` providers are excluded from auto-routing.
- The FiinQuantX OHLCV adapter accepts only bounded, verified request
  controls and retains only canonical output columns.
- The final focused suite passed: 125 tests; Ruff check/format and strict
  OpenSpec validation also passed. The bounded licensed live suite passed:
  2 tests.
- Local HTTP smoke on the final deployed image passed for bounded OHLCV,
  membership snapshot, disabled company information, rejected credential-like
  query input, rejected unverified OHLCV control, and forbidden auth route.

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
| G1 optional provider foundation | uncommitted tree based on `1de8636faed167b7fb0c7b038153eaeeb83f09ce` | partial | Lazy exact-version plugin, approval, capability, error-mapping and forbidden-surface tests pass offline; licensed runtime remains not run |
| G2 reference and historical market | uncommitted tree based on `1de8636faed167b7fb0c7b038153eaeeb83f09ce` | partial | Gate A bounded equity/index OHLCV and current membership contracts, UTC timestamps, strict service validation, persistence and canonical-basis tests pass offline; licensed probes remain not run; Gate B/C remain disabled |
| G3 flow/ownership/market structure/valuation | pending | not run | pending |
| G4 period-aware fundamentals | pending | not run | pending |
| G5 namespaced vendor analytics | pending | not run | pending |
| G6 streaming architecture | pending | deferred to separate accepted change or not run |
| G7 full offline/package/live/OpenSpec | uncommitted tree based on `1de8636faed167b7fb0c7b038153eaeeb83f09ce` | partial | `PYTHONPATH=. uv run pytest -q -m 'not integration'`: 1371 passed, 53 live skips, 93 deselected; Debian package 59/59; strict OpenSpec valid; licensed/live and exact-candidate host evidence remain not run |
