# vnstock Roadmap — Plugin-based Data Platform Services

> Goal: evolve `vnstock` from a Python market data SDK into a **plugin-based, auth-aware, quality-first financial data platform** for Vietnamese and global market data research.
>
> Architecture constraint: **data-only**. No broker execution, no order placement, no account/portfolio APIs, no trading bots, no stock recommendation engine, and no strategy/pattern scanner in core `vnstock`.

---

## 0. Strategic direction

`vnstock` should become the **Vietnam Open Financial Data Platform** layer.

It should serve multiple consumers:

```text
Python SDK
REST API
CLI/TUI data console
MCP data tools
notebooks
batch ingestion jobs
vnalpha workspace
AI agents that need market data
```

`vnstock` should own:

```text
provider plugins
dataset contracts
schema normalization
data quality validation
provider diagnostics
provider comparison
health-aware routing
auth/session management for credentialed data providers
rate limiting
cache
batch ingestion
raw/normalized archive
storage sinks
REST API
CLI/TUI data console
MCP data server
```

`vnstock` should not own:

```text
trading signal generation
stock recommendation
pattern scanner
portfolio optimizer
broker execution
order placement
trading bot
investment advice workflow
```

Analysis and research workflows such as pattern detection, watchlists, backtests, AI analyst reports, and trading journals should live in `vnalpha`.

---

## Current state snapshot

The current codebase already has important data-foundation components:

```text
Unified UI over Market, Reference, Fundamental, and Retail
KBS/VCI/DNSE/TCBS support for core Vietnamese equity market paths
memory/SQLite cache layer
data quality layer for OHLCV, price board, and intraday trades
provider hardening layer with capability registry, drift detection, OHLCV comparison, health scoring, and matrix support
provider contract fixtures/tests
live smoke test scaffold gated by VNSTOCK_LIVE_TESTS
CI for Ruff, format check, offline pytest, and build
```

The next priority is to formalize these capabilities into stable platform contracts.

---

# Phase 1 — Core contracts and internal plugin foundation

**Phase 1 is closed.** `ProviderPlugin` protocol, `PluginRegistry`, `DataResult`,
and `CONTRACT_REGISTRY` (twelve datasets) are implemented and regression-tested.
See `docs/PLUGIN_ARCHITECTURE_STATUS.md` for the full closure record.

## Goal

Create the internal plugin architecture inside the monorepo first. Do not split external packages yet.

## 1.1. Define dataset contracts

Standardize dataset names and schemas.

Initial dataset contracts:

```text
equity.ohlcv
equity.quote
equity.intraday_trades
index.ohlcv
reference.symbols
reference.company_info
reference.industry
fundamental.balance_sheet
fundamental.income_statement
fundamental.cash_flow
fundamental.financial_ratio
fund.nav
foreign_flow.daily
```

Each dataset contract should define:

```text
dataset name
required columns
optional columns
dtype rules
timezone policy
time column format
symbol format
price scale expectation
volume/value unit expectation
freshness expectation
validator binding
provider capability declaration
```

Example contract concept:

```python
class OHLCVContract:
    dataset = "equity.ohlcv"
    required_columns = [
        "symbol",
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    optional_columns = [
        "value",
        "provider",
        "fetched_at",
        "adjusted",
    ]
```

## 1.2. Define `ProviderPlugin` interface

```python
class ProviderPlugin:
    name: str

    def capabilities(self) -> dict:
        ...

    def fetch(self, dataset: str, params: dict):
        ...

    def validate_params(self, dataset: str, params: dict) -> None:
        ...

    def diagnostics(self) -> dict:
        ...
```

## 1.3. Define `ProviderRegistry`

```python
class ProviderRegistry:
    def register(self, provider: ProviderPlugin):
        ...

    def get(self, name: str) -> ProviderPlugin:
        ...

    def providers_for(self, dataset: str) -> list[ProviderPlugin]:
        ...
```

## 1.4. Define `DataResult`

Do not rely only on anonymous `DataFrame` returns for platform internals.

```python
@dataclass
class DataResult:
    dataset: str
    provider: str
    data: pd.DataFrame
    quality_status: str | None
    quality_report: dict | None
    diagnostics: dict | None
    fetched_at: datetime
    ingestion_run_id: str | None = None
```

For backward compatibility, public UI methods may still return `DataFrame`, but internal flows should use `DataResult` or attach equivalent metadata to `DataFrame.attrs`.

## 1.5. Preserve current public API

Current user-facing usage should remain stable:

```python
from vnstock import Market

market = Market()

bars = market.equity.ohlcv(
    symbol="FPT",
    start="2024-01-01",
    end="2026-07-03",
    interval="1D",
    validate=True,
)
```

Internally, the call should go through:

```text
Market UI
→ ProviderRouter
→ ProviderRegistry
→ ProviderPlugin
→ DatasetContract
→ Validator
→ DataFrame + metadata
```

## Deliverables

```text
vnstock/core/contracts/
vnstock/core/provider/plugin.py
vnstock/core/provider/registry.py
vnstock/core/provider/router.py
vnstock/core/result.py
tests/unit/core/provider/
tests/contracts/
```

## Exit criteria

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

---

# Phase 2 — Normalize existing providers as internal plugins

**Phase 2 is closed.** All seven built-in providers (KBS, VCI, DNSE, TCBS,
FMARKET, MSN, FMP) satisfy `ProviderPlugin`, are registered through
`default_plugin_registry()`, and pass provider conformance tests.
See `docs/PLUGIN_ARCHITECTURE_STATUS.md` for the full closure record.

## Goal

Move KBS, VCI, DNSE, TCBS, MSN, FMP, and FMarket toward the same provider plugin interface.

## 2.1. Provider module structure

Target structure:

```text
vnstock/providers/
├── kbs/
│   ├── plugin.py
│   ├── client.py
│   ├── normalize.py
│   └── contracts.py
├── vci/
├── dnse/
├── tcbs/
├── fmarket/
├── msn/
└── fmp/
```

## 2.2. Capability declarations

Each provider should declare supported datasets explicitly.

Example:

```python
class TCBSProvider:
    name = "TCBS"

    def capabilities(self):
        return {
            "equity.ohlcv": {
                "supported": True,
                "intervals": ["1D"],
                "auth_required": False,
                "status": "experimental",
            },
            "equity.quote": {
                "supported": True,
                "auth_required": False,
            },
            "fundamental.balance_sheet": {
                "supported": True,
                "auth_required": False,
            },
        }
```

## 2.3. Provider limitations metadata

Each provider should expose:

```text
supported datasets
supported intervals
known limitations
rate limit profile
auth requirement
freshness expectation
schema drift risk
coverage gaps
```

## 2.4. Provider contract tests

Add offline fixtures for:

```text
valid response
empty but valid response
invalid symbol
suspended symbol
newly listed symbol
non-trading day
partial intraday session
missing optional fields
unexpected extra fields
provider schema drift
```

## Deliverables

```text
providers/*/plugin.py
providers/*/fixtures/
tests/contracts/providers/
provider capability matrix generator
```

## Exit criteria

```text
All core providers implement the same interface.
Unified UI remains backward compatible.
Provider capability matrix can be generated.
Offline contract tests pass.
```

---

# Phase 3 — Health-aware routing and diagnostics

**Phase 3 is closed.** `PluginRouter` implements health-aware and auth-aware
routing with tiered fallback, cooldown, explicit source overrides, and full
`RoutingDecision` audit trail. See `docs/PLUGIN_ARCHITECTURE_STATUS.md` for
the full closure record.

## Goal

Make `source="auto"` choose providers by capability, health, freshness, auth policy, and cooldown, not only round-robin behavior.

## 3.1. Provider health model

```python
@dataclass
class ProviderHealth:
    provider: str
    dataset: str
    status: str  # HEALTHY | DEGRADED | FAILING | UNKNOWN
    latency_ms: float | None
    error_rate: float | None
    freshness_score: float | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
```

## 3.2. Routing policy

```text
source="TCBS"
  → force TCBS, but emit warning if degraded

source="auto"
  → choose by:
     dataset capability
     auth policy
     provider health
     freshness
     cooldown
     configured priority
```

## 3.3. Diagnostics metadata

`DataResult.diagnostics` or `DataFrame.attrs` should include:

```text
selected_provider
candidate_providers
routing_reason
provider_health
fallback_used
validation_summary
```

## 3.4. Provider comparison expansion

Current comparison should be expanded beyond OHLCV.

Target comparison APIs:

```text
compare_ohlcv
compare_quote
compare_intraday_shape
compare_coverage
compare_freshness
```

## Deliverables

```text
Health-aware ProviderRouter
ProviderHealthStore
ProviderDiagnostics
compare_quote()
compare_intraday_shape()
provider matrix report
```

## Exit criteria

```text
source="auto" chooses providers by health.
Degraded providers are used only as fallback unless forced.
Provider failures trigger cooldown.
Diagnostics explain the selected provider.
Tests simulate healthy/degraded/failing providers.
```

---

# Phase 4 — Auth and credential-aware providers

## Goal

Support providers that require login, API keys, OAuth, client certificates, or manual sessions while preserving the data-only boundary.

## 4.1. Auth types

```python
class AuthType(str, Enum):
    NO_AUTH = "no_auth"
    API_KEY = "api_key"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    SESSION_COOKIE = "session_cookie"
    CLIENT_CERTIFICATE = "client_certificate"
    MANUAL_INTERACTIVE = "manual_interactive"
```

## 4.2. AuthSpec

```python
@dataclass
class AuthSpec:
    auth_type: AuthType
    required: bool
    scopes: list[str]
    credential_ref: str | None = None
    refreshable: bool = False
    interactive_required: bool = False
    ttl_seconds: int | None = None
```

## 4.3. Credential stores

Implement:

```text
MemoryCredentialStore
EnvCredentialStore
KeyringCredentialStore
VaultCredentialStore
EncryptedFileCredentialStore, optional and not default
```

Never store:

```text
passwords in config files
tokens in logs
cookies in DataFrame attrs
secrets in MCP tool inputs
secrets in notebooks
```

## 4.4. AuthManager

```python
class AuthManager:
    def get_auth_context(self, provider: str, dataset: str):
        ...

    def login(self, provider: str, mode: str = "interactive"):
        ...

    def logout(self, provider: str):
        ...
```

## 4.5. Auth policies

```text
prefer_no_auth
allow_authenticated
require_authenticated
forbid_authenticated
```

Example:

```python
bars = market.equity.ohlcv(
    symbol="FPT",
    source="auto",
    auth_policy="allow_authenticated",
)
```

## 4.6. CLI auth commands

```bash
vnstock auth status
vnstock auth set PROVIDER --type api-key
vnstock auth login PROVIDER
vnstock auth logout PROVIDER
vnstock auth delete PROVIDER
```

## 4.7. Hard compliance boundaries

Credentialed data access is allowed only for data-read use cases.

`vnstock` must not implement:

```text
broker order placement
broker account APIs
portfolio APIs
CAPTCHA bypass
2FA bypass
anti-bot bypass
credential sharing across users
```

## Deliverables

```text
vnstock/core/auth/
CredentialStore
AuthManager
AuthContext
AuthSpec
redaction middleware
CLI auth commands
auth-aware router
```

## Exit criteria

```text
API key provider flow works.
Auth metadata is visible without exposing secrets.
Logs redact sensitive headers/cookies/tokens.
MCP/API/TUI never accept raw secrets as input.
Broker/account/order endpoints remain out of scope.
```

---

# Phase 3.5 and Phase 4 — Closure status

**Phase 3.5** is closed. Service data endpoints no longer bypass `PluginRuntime`.
All supported data endpoints route through `PluginRuntime.fetch(..., return_result=True)`.
Tests fail if the runtime is bypassed.

**Phase 4** is closed. The `vnstock-serve` local data service:

- exposes canonical `/v1/<domain>/<dataset>` read-only endpoints
- routes all data fetches through `PluginRuntime`
- returns a stable `data` / `meta` / `diagnostics` response envelope
- uses the plugin registry for provider metadata endpoints
- exposes safe auth status without credential material
- keeps REST login/logout, broker, account, portfolio, trading, and order endpoints permanently forbidden
- supports localhost-only deployment via Docker

---

# Phase 5 — Rate limiter, retry, and batch result envelope

## Goal

Support full-market ingestion without uncontrolled provider calls and with structured partial failure handling.

## 5.1. Rate limiter

Implement:

```text
provider-scoped throttling
endpoint-scoped throttling
token bucket or sliding window limiter
jittered retry/backoff
cooldown on 429/timeout
metrics hooks
```

Suggested env config:

```bash
VNSTOCK_RATE_LIMIT_ENABLED=true
VNSTOCK_RATE_LIMIT_KBS_PER_MINUTE=60
VNSTOCK_RATE_LIMIT_VCI_PER_MINUTE=60
VNSTOCK_RATE_LIMIT_DNSE_PER_MINUTE=60
```

## 5.2. Batch OHLCV API

Target:

```python
result = Market().equity.history_batch(
    symbols=["FPT", "VCB", "TCB"],
    start="2024-01-01",
    end="2026-07-03",
    interval="1D",
    source="auto",
    validate=True,
    fail_fast=False,
)
```

Batch result:

```python
@dataclass
class BatchResult:
    data: dict[str, pd.DataFrame]
    errors: dict[str, Exception | str]
    quality: dict[str, dict]
    provider_used: dict[str, str]
    diagnostics: dict[str, dict]
```

## 5.3. Partial failure behavior

```text
fail_fast=False:
  keep fetching other symbols
  store per-symbol errors
  return partial result envelope

fail_fast=True:
  stop at first error
```

## Deliverables

```text
RateLimiter
RetryPolicy
BatchResult
history_batch()
batch diagnostics
provider request metrics
```

## Exit criteria

```text
Full-market batch scan runs with bounded provider calls.
Partial failures are inspectable.
Provider/rate-limit metrics can be reported.
No unbounded retry behavior.
```

---

# Phase 6 — Raw archive, normalized archive, and storage sinks

## Goal

Make `vnstock` reproducible, replayable, and auditable as a data platform.

## 6.1. Raw archive

Persist raw provider responses before normalization:

```text
raw/provider=KBS/dataset=ohlcv/symbol=FPT/date=2026-07-03.json
normalized/provider=KBS/dataset=ohlcv/symbol=FPT/interval=1D.parquet
```

## 6.2. StorageSink interface

```python
class StorageSink:
    def write(self, dataset: str, frame, metadata: dict) -> None:
        ...

    def read(self, dataset: str, query: dict):
        ...
```

Implement:

```text
ParquetSink
DuckDBSink
SQLiteMetadataSink
PostgresSink
```

## 6.3. Ingestion run manifest

```sql
ingestion_run(
    id,
    dataset,
    started_at,
    finished_at,
    status,
    config_json,
    summary_json
)
```

## 6.4. Normalized market table

```sql
market_ohlcv(
    symbol,
    time,
    interval,
    open,
    high,
    low,
    close,
    volume,
    provider,
    fetched_at,
    quality_status,
    quality_report_json,
    provider_diagnostics_json,
    PRIMARY KEY(symbol, time, interval, provider)
)
```

## 6.5. Incremental sync

Support:

```text
sync by symbol/date range
gap detection before fetch
idempotent upsert
revalidation without refetching raw data
run manifest per sync job
```

## Deliverables

```text
raw archive writer
ParquetSink
DuckDBSink
PostgresSink
ingestion_run metadata
incremental sync
gap detection
idempotent upsert
```

## Exit criteria

```text
Historical OHLCV sync is rerunnable and idempotent.
Raw response can be replayed/reparsed.
Quality reports are stored with data.
Lineage is traceable by provider and fetch timestamp.
```

---

# Phase 7 — REST data service: `vnstock-api`

## Goal

Create an optional service surface. The service should wrap the same core SDK/platform layer.

## 7.1. Data endpoints

```text
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/equity/intraday
GET /v1/index/ohlcv
GET /v1/company/info
GET /v1/fundamental/balance-sheet
GET /v1/fundamental/income-statement
```

## 7.2. Provider endpoints

```text
GET /v1/providers
GET /v1/providers/health
GET /v1/providers/capabilities
GET /v1/providers/compare/ohlcv
```

## 7.3. Ingestion endpoints

```text
POST /v1/ingestion/sync/ohlcv
GET /v1/ingestion/runs/{run_id}
GET /v1/ingestion/runs/{run_id}/errors
```

## 7.4. Auth endpoints

The service exposes safe auth status only. REST login/logout are explicitly out of scope.

```text
GET /v1/auth/providers
GET /v1/auth/status
GET /v1/auth/{provider}/status
```

The following endpoints MUST NOT exist in the data service:

```text
POST /v1/auth/{provider}/login   — out of scope; use CLI: vnstock auth login
POST /v1/auth/{provider}/logout  — out of scope; use CLI: vnstock auth logout
```

Authentication credentials are managed through `vnstock-auth` CLI commands,
not through REST endpoints. The local data service is data-read only.

## 7.5. Response envelope

```json
{
  "dataset": "equity.ohlcv",
  "symbol": "FPT",
  "provider": "KBS",
  "quality_status": "PASS",
  "data": [],
  "quality_report": {},
  "diagnostics": {},
  "fetched_at": "2026-07-03T18:05:00+07:00"
}
```

## Deliverables

```text
vnstock/api/
FastAPI app
OpenAPI docs
data endpoints
provider endpoints
auth status endpoints
docker-compose example
```

## Exit criteria

```text
vnalpha can consume vnstock through HTTP.
OpenAPI schema is generated.
Health endpoint works.
API does not expose secrets.
```

---

# Phase 8 — CLI and TUI data console

## Goal

Create a data operations console, not a trading terminal.

## 8.1. CLI commands

```bash
vnstock fetch FPT --dataset equity.ohlcv
vnstock quote FPT,VCB,TCB
vnstock validate FPT
vnstock compare FPT --sources KBS,VCI,TCBS
vnstock health
vnstock sync --universe hose
vnstock auth status
```

## 8.2. TUI screens

```text
Provider Health
Capability Matrix
Symbol Explorer
Quality Report Viewer
Provider Comparison
Batch Ingestion Monitor
Auth Status
Raw Archive Browser
```

## 8.3. Explicit non-goals for TUI

The TUI must not implement:

```text
breakout scanner
stock recommendation
buy/sell workflow
portfolio screen
broker execution
trading bot
```

These belong in `vnalpha` if needed.

## Deliverables

```text
vnstock/cli/
vnstock/tui/
Textual or Rich-based TUI
command palette
provider health dashboard
quality report viewer
batch monitor
```

## Exit criteria

```text
CLI supports data ops workflows.
TUI can inspect providers, data, and quality.
No trading analysis or execution features are added.
```

---

# Phase 9 — MCP server: `vnstock-mcp`

## Goal

Make `vnstock` an AI-agent-ready data source.

## 9.1. MCP tools

```text
get_ohlcv
get_quote
get_company_info
get_financial_statement
validate_ohlcv
compare_provider
get_provider_health
search_symbols
```

## 9.2. MCP guardrails

MCP tools must not accept:

```text
api_key
password
cookie
access_token
refresh_token
```

MCP tools must not include:

```text
recommend_stock
place_order
scan_buy_signal
optimize_portfolio
```

## 9.3. Tool response format

```json
{
  "dataset": "equity.ohlcv",
  "symbol": "FPT",
  "provider": "KBS",
  "quality_status": "PASS",
  "rows": 512,
  "data_preview": [],
  "diagnostics": {}
}
```

## Deliverables

```text
vnstock/mcp/
MCP server
tool registry
auth guard
redaction guard
tool schemas
```

## Exit criteria

```text
AI agents can call data tools through MCP.
No secrets appear in tool input/output.
Tools remain data-only.
```

---

# Phase 10 — External plugin packages

## Goal

After internal contracts are stable, split providers/storage/surfaces into external packages.

Do not do this before contracts are stable.

## 10.1. Candidate packages

```text
vnstock-core
vnstock-provider-kbs
vnstock-provider-vci
vnstock-provider-dnse
vnstock-provider-tcbs
vnstock-provider-fmarket
vnstock-storage-duckdb
vnstock-storage-postgres
vnstock-api
vnstock-mcp
vnstock-tui
```

## 10.2. Entry point discovery

`pyproject.toml` of a provider plugin:

```toml
[project.entry-points."vnstock.providers"]
tcbs = "vnstock_provider_tcbs:TCBSProvider"
vci = "vnstock_provider_vci:VCIProvider"
dnse = "vnstock_provider_dnse:DNSEProvider"
```

Core plugin loader:

```python
from importlib.metadata import entry_points

def load_provider_plugins():
    eps = entry_points(group="vnstock.providers")
    for ep in eps:
        provider_cls = ep.load()
        registry.register(provider_cls())
```

## 10.3. Version compatibility

Track:

```text
core contract version
dataset schema version
provider plugin version
API version
MCP tool version
```

## Deliverables

```text
entry point loader
plugin version compatibility checks
plugin metadata schema
provider plugin template
external provider example
```

## Exit criteria

```text
External provider package can be installed by pip.
Core discovers the plugin automatically.
Contract tests can run against external plugins.
Version compatibility is explicit.
```

---

# Phase 11 — Integration contract with `vnalpha`

## Goal

Allow `vnalpha` to consume `vnstock` in two modes:

```text
SDK mode
Service mode
```

## 11.1. SDK mode

```python
client = VnstockSdkClient()
```

Use for local MVP and notebooks.

## 11.2. Service mode

```python
client = VnstockServiceClient(base_url="http://localhost:6900")
```

Use for platform deployments, credentialed providers, shared cache, shared rate limit, and MCP/data-service scenarios.

## 11.3. Config

```yaml
data_layer:
  mode: sdk  # sdk | service
  service_url: http://localhost:6900
  auth_policy: allow_authenticated
  validate: true
```

## 11.4. Data contract for `vnalpha`

```python
@dataclass
class DataResult:
    dataset: str
    provider: str
    data: pd.DataFrame
    quality_status: str
    quality_report: dict
    diagnostics: dict
    fetched_at: datetime
    ingestion_run_id: str | None
```

`vnalpha` should build its research warehouse from this result:

```text
market_ohlcv
canonical_ohlcv
daily_feature
pattern_instance
pattern_outcome
```

## Exit criteria

```text
vnalpha does not call provider endpoints directly.
vnalpha works in both SDK mode and service mode.
Quality metadata flows into the research layer.
```

---

# Phase 12 — Documentation, governance, and release model

## Goal

Make the platform maintainable for long-term development.

## 12.1. Required docs

```text
Plugin architecture guide
Provider development guide
Dataset contract reference
Auth and secrets policy
Storage sink guide
API reference
MCP tool reference
CLI/TUI guide
vnalpha integration guide
```

## 12.2. CI/CD

```text
offline tests
contract tests
provider fixture tests
quality validator tests
API tests
MCP tool schema tests
build package
optional live smoke tests gated by env
```

## 12.3. Release channels

```text
dev
beta
stable
```

---

# Suggested implementation priority

## Must do first

```text
1. Dataset contracts
2. ProviderPlugin interface
3. ProviderRegistry
4. DataResult envelope
5. Normalize existing providers
6. Contract tests
7. Health-aware router
8. BatchResult
```

## Then platformize

```text
9. Auth Manager
10. Rate limiter
11. Raw archive
12. Storage sinks
13. REST API
14. MCP server
15. CLI/TUI data console
```

## Then externalize

```text
16. Entry point plugin discovery
17. External provider packages
18. Plugin templates
19. Public plugin documentation
```

---

# Recommended 90-day plan

## Month 1 — Plugin foundation

```text
Week 1:
- define dataset contracts
- define DataResult
- define ProviderPlugin interface

Week 2:
- create ProviderRegistry
- create ProviderRouter skeleton
- adapt one provider, e.g. TCBS or KBS

Week 3:
- adapt remaining core providers
- add provider capability matrix

Week 4:
- contract tests
- backward compatibility checks
- docs for internal provider interface
```

## Month 2 — Reliability runtime

```text
Week 5:
- provider health model
- health-aware router

Week 6:
- compare_ohlcv hardening
- quote/intraday comparison skeleton

Week 7:
- rate limiter
- retry/backoff
- cooldown integration

Week 8:
- history_batch
- BatchResult envelope
- full-market partial failure report
```

## Month 3 — Data platform services

```text
Week 9:
- raw archive
- ParquetSink
- DuckDBSink

Week 10:
- ingestion_run manifest
- incremental sync
- gap detection

Week 11:
- FastAPI service MVP
- provider health endpoint
- OHLCV endpoint
- quality report endpoint

Week 12:
- vnalpha SDK/service client contract
- MCP data tools skeleton
- documentation update
```

---

# Main risks and mitigations

## Risk 1 — Over-engineering

Plugin architecture can slow development if external packages are split too early.

Mitigation:

```text
Keep internal plugin architecture in monorepo first.
Split packages only after contracts stabilize.
```

## Risk 2 — Weak schema normalization

Provider plugins are not useful if dataset contracts are loose.

Mitigation:

```text
Dataset contracts first.
Provider contract tests mandatory.
Quality validators mandatory.
```

## Risk 3 — Auth providers pull `vnstock` into broker/trading territory

Credentialed providers may tempt account/order integration.

Mitigation:

```text
Data-read scope only.
No broker execution.
No account/order APIs.
No CAPTCHA/2FA bypass.
Credential store + redaction mandatory.
```

## Risk 4 — API/TUI/MCP bypass the core

Surfaces that call provider endpoints directly will break platform governance.

Mitigation:

```text
All surfaces must call vnstock core.
Provider direct access is allowed only inside provider plugins.
```

## Risk 5 — AI hallucination on low-quality data

MCP/AI agents may summarize bad data confidently.

Mitigation:

```text
MCP always returns quality_status.
AI tools must expose provider + quality metadata.
No PASS/WARN_ACCEPTED quality means no confident summary.
```

---

# Final target architecture

```text
vnstock-core
  ├── dataset contracts
  ├── provider registry
  ├── health-aware router
  ├── auth manager
  ├── quality validators
  ├── cache
  ├── rate limiter
  ├── batch ingestion
  └── storage interfaces

vnstock-provider-*
  ├── KBS
  ├── VCI
  ├── DNSE
  ├── TCBS
  ├── FMarket
  └── future credentialed providers

vnstock-services
  ├── REST API
  ├── CLI
  ├── TUI
  └── MCP server

vnalpha
  ├── canonical data
  ├── feature store
  ├── pattern engine
  ├── backtest
  ├── AI analyst
  └── workspace
```

## One-line strategy

```text
Move vnstock from a data SDK into a plugin-based, auth-aware, quality-first financial data platform; keep analysis and trading research in vnalpha.
```
