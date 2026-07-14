# Design: FiinQuantX Provider Integration

## Architectural position

FiinQuantX is an optional commercial provider inside the existing `vnstock` provider platform.

```text
Market / Reference / Fundamental UI
or vnstock local REST service
        ↓
PluginRuntime.fetch(dataset, params, return_result=True)
        ↓
PluginRouter
        ↓
PluginRegistry
        ↓
FiinQuantXProviderPlugin
        ↓
licensed fiinquantx SDK
        ↓
provider-specific normalization
        ↓
DatasetContract validation
        ↓
DataResult + diagnostics + lineage
```

The provider is not a new data-access architecture. It must not bypass `PluginRuntime`, duplicate auth handling, or create a direct FiinQuantX path in `vnalpha`.

## Package layout

Target package-relative layout:

```text
vnstock/providers/fiinquantx/
├── __init__.py
├── plugin.py
├── sdk.py
├── auth.py
├── capabilities.py
├── entitlement.py
├── rate_limit.py
├── exceptions.py
├── diagnostics.py
├── mappings.py
└── normalize/
    ├── market.py
    ├── reference.py
    ├── ownership.py
    ├── valuation.py
    └── fundamentals.py
```

Test areas:

```text
tests/unit/providers/fiinquantx/
tests/contracts/providers/test_fiinquantx_contract.py
tests/live/providers/test_fiinquantx_live.py
tests/fixtures/providers/fiinquantx/synthetic/
```

Documentation areas:

```text
docs/providers/FIINQUANTX.md
docs/PROVIDER_HARDENING.md
roadmap.md
examples/fiinquantx_example.py
```

## FQ-0: licensed contract discovery

### Purpose

The public repository exposes only a wheel index. The first implementation slice must establish the actual SDK contract using a licensed environment and official documentation.

### Discovery tooling

Add a developer-only contract inventory script that:

- imports the installed SDK lazily;
- records installed version and import path;
- enumerates approved public classes/functions without serializing secrets;
- records call signatures where introspection is supported;
- executes a minimal approved dataset matrix using a small symbol/date scope;
- writes redacted shape metadata only;
- never writes raw licensed values by default.

Example output shape:

```json
{
  "provider": "FIINQUANTX",
  "sdk_version": "0.1.64",
  "python_version": "3.12.x",
  "datasets": {
    "equity.ohlcv": {
      "method": "verified public method name",
      "parameters": ["symbol", "start", "end", "interval"],
      "columns": ["..."],
      "dtypes": {"...": "..."},
      "timezone": "...",
      "entitled": true
    }
  }
}
```

The committed repository may contain only a reviewed, manually redacted contract summary and synthetic fixtures. It must not contain proprietary source, docs, credentials, or production records.

### Version policy

Initial implementation shall pin and validate one exact FiinQuantX SDK version. The provider must expose the tested version in diagnostics.

A newer installed version may run only when:

- it satisfies the configured compatibility policy;
- contract fixture/schema checks pass;
- no known incompatible method or field drift is detected.

Unknown major/minor compatibility must fail closed with an installation/compatibility diagnostic rather than silently continuing.

## Provider plugin contract

```python
class FiinQuantXProviderPlugin:
    name = "FIINQUANTX"

    def capabilities(self) -> dict[str, dict]: ...
    def auth_spec(self, dataset: str) -> AuthSpec: ...
    def validate_params(self, dataset: str, params: dict) -> None: ...
    def fetch(self, dataset: str, params: dict) -> pandas.DataFrame: ...
    def diagnostics(self) -> dict: ...
```

### Lazy SDK loading

Importing `vnstock` or constructing the default plugin registry must not fail when FiinQuantX is not installed.

The plugin loader must distinguish:

```text
not installed
installed but incompatible
installed but unauthenticated
installed and authenticated but dataset not entitled
installed, entitled, healthy
```

### Optional dependency

The base package must not vendor the wheel. The installation documentation shall reference the official FiinQuantX distribution mechanism verified during FQ-0.

The project may define an optional dependency marker or installation extra only if the commercial package can be declared without redistributing it. Otherwise, documentation and runtime discovery shall treat it as an externally installed optional package.

## Authentication and secret handling

### Auth model

The provider must map the verified SDK login/session mechanism into the existing auth abstractions.

Credentials may be read from:

- the existing environment credential store;
- the existing keyring/credential manager where supported;
- an explicit local interactive CLI auth flow if required by the SDK.

Credentials must not be accepted in REST, MCP, TUI command arguments, DataFrame attributes, or assistant tool parameters.

### Redaction

The following are forbidden in logs and diagnostics:

```text
username
password
access token
refresh token
session token
cookie
API key
account/customer identifier
raw auth response
```

Public diagnostics may include only safe state:

```text
provider installed
auth configured
authenticated yes/no
subscription active/expired/unknown
entitled dataset names
quota percentage or safe aggregate where allowed
SDK version
last success/failure timestamps
```

## Entitlement-aware capabilities

FiinQuantX capability is a conjunction of:

```text
SDK method exists
AND local provider mapping exists
AND account entitlement permits the dataset
AND version/schema compatibility is accepted
```

The static capability declaration represents implemented adapter support. Runtime diagnostics represent current entitlement.

`PluginRouter` shall not select FiinQuantX for a dataset when entitlement is known to be absent.

Typed outcomes:

```text
FiinQuantXNotInstalledError
FiinQuantXVersionError
FiinQuantXAuthenticationError
FiinQuantXEntitlementError
FiinQuantXQuotaError
FiinQuantXRateLimitError
FiinQuantXSchemaError
FiinQuantXProviderError
```

All errors are wrapped into existing platform exceptions before leaving the provider boundary.

## Dataset strategy

### Existing contracts first

Initial adapters should target current contracts to prove architecture compatibility:

```text
reference.symbols
equity.ohlcv
index.ohlcv
equity.quote
fundamental.balance_sheet
fundamental.income_statement
fundamental.cash_flow
fundamental.financial_ratio
foreign_flow.daily
```

Only datasets verified in FQ-0 are enabled.

### New contract candidates

The following contracts may be added after raw SDK verification:

```text
reference.index_constituents
reference.free_float_history
reference.share_outstanding
reference.foreign_ownership_limit
market.market_cap_history
market.breadth
valuation.history
foreign_flow.intraday
equity.order_book_snapshot
equity.aggressor_flow
indicator.vendor_derived
```

Each new contract must define:

- required and optional fields;
- symbol/entity normalization;
- time/date and timezone semantics;
- units and scale;
- freshness expectation;
- uniqueness key;
- revision and restatement behavior;
- validator binding;
- provider capability declaration.

## Canonical normalization

Provider-specific columns remain inside the FiinQuantX normalization package. Public platform consumers receive canonical contracts.

Every normalized result must attach safe metadata:

```text
provider=FIINQUANTX
dataset
sdk_version
fetched_at
request_window
provider_dataset/method identifier
quality_status
validation summary
routing decision
entitlement state
```

Do not attach secrets, raw auth state, or proprietary request payloads.

## Publication-aware fundamentals

A financial statement is not historically usable merely because a fiscal period exists.

Where supported by the SDK, normalized fundamentals must preserve:

```text
symbol
fiscal_period_end
period_type
published_at or available_from
consolidation_scope
audit_status
restatement/version identity
currency
unit
provider record identity
fetched_at
```

If the feed does not provide a defensible publication/availability timestamp, the result must expose that limitation and must not be advertised as suitable for historical as-of analysis.

Original and restated versions must not be silently overwritten when the source exposes revision identity.

## Vendor-derived indicators

FiinQuantX-calculated indicators remain vendor-derived unless OpenStock independently defines and validates the formula.

```text
indicator.vendor_derived
```

shall preserve:

- vendor indicator code/name;
- value and unit;
- effective period/date;
- vendor formula/version metadata when available;
- provider/source lineage.

Vendor indicators must not silently replace deterministic OpenStock feature or scoring formulas.

## Rate, connection, and quota control

The provider adapter shall expose verified limit metadata and cooperate with platform rate control.

Required controls when supported by the commercial plan:

- provider-scoped request limiter;
- connection/session semaphore;
- bounded timeout;
- bounded retry with jitter for explicitly retryable failures;
- no retry for auth, entitlement, invalid request, or incompatible version;
- cooldown after repeated provider failures;
- quota preflight for bounded batch operations;
- partial batch results rather than unbounded fail/retry loops.

`source=auto` should avoid spending commercial quota when a configured public provider is sufficient for a non-authoritative request, unless routing policy explicitly prefers FiinQuantX.

## Caching, persistence, and redistribution policy

The implementation must include a license decision record for each behavior:

```text
in-memory cache
SQLite cache
raw archive
normalized local persistence
DuckDB/Postgres sink
local REST response
multi-user service exposure
bulk export
synthetic test fixtures
derived analytics
```

Default until approved:

- local in-process use allowed only under the licensed account;
- raw archive disabled;
- bulk export disabled;
- public/multi-user service exposure disabled;
- synthetic fixtures only in Git;
- normalized persistence enabled only after license confirmation.

## Routing policy

### Explicit source

```text
source="FIINQUANTX"
```

must never silently fall back to another provider. It returns a typed FiinQuantX installation, auth, entitlement, quota, compatibility, or data failure.

### Auto source

For `source="auto"`, the router considers:

- dataset support;
- entitlement;
- auth policy;
- configured provider priority;
- health and cooldown;
- freshness;
- quota budget;
- license/deployment policy.

Routing diagnostics must explain why FiinQuantX was selected or rejected without exposing secrets.

## Service surface

The existing local REST service may expose FiinQuantX-normalized data through canonical read-only endpoints only when deployment policy permits.

No FiinQuantX-specific login endpoint is added to REST.

Provider metadata endpoints may report safe installation, capability, health, and entitlement status.

## Validation strategy

### Offline

Synthetic fixtures shall cover:

- valid response;
- valid empty response;
- invalid symbol;
- unsupported interval;
- missing optional fields;
- schema drift;
- not installed;
- incompatible SDK version;
- unauthenticated session;
- expired subscription;
- missing entitlement;
- quota/rate-limit failure;
- transient provider failure;
- fundamentals without publication time;
- restated financial record;
- canonical normalization and metadata redaction.

### Live

Live tests are disabled by default and require explicit licensed opt-in:

```text
VNSTOCK_LIVE_TESTS=true
VNSTOCK_LIVE_PROVIDERS=FIINQUANTX
VNSTOCK_FIINQUANTX_LICENSED=true
```

Live tests must use a minimal symbol/date scope and must not dump raw payloads to CI logs.

### Cross-provider comparison

For overlapping data, compare FiinQuantX against KBS/VCI or another approved provider for:

- date coverage;
- OHLC values and price scale;
- volume/value units;
- symbol mapping;
- corporate-action adjustment status;
- statement periods and units;
- foreign-flow direction/sign conventions.

Differences create typed comparison diagnostics. They must not be silently reconciled.

## Backward compatibility

- Existing public `Market`, `Reference`, `Fundamental`, and `Retail` calls remain valid.
- Existing provider names and explicit source selection remain unchanged.
- The base package imports without FiinQuantX installed.
- Existing provider routing continues when FiinQuantX is unavailable.
- No legacy provider is removed by this change.

## Read-only boundary

The FiinQuantX adapter must expose data retrieval only.

Even if the commercial SDK contains adjacent trading functionality, the adapter must not import, declare, route, or expose broker, account, portfolio, order, margin, transfer, or execution methods.