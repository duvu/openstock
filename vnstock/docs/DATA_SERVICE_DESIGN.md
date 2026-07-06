# vnstock Data Service Design

## Purpose

`vnstock-service` is a local-first, Docker-ready, data-read-only financial data service.

It turns `vnstock` from a Python-only market data toolkit into an independent data platform service that can be consumed by notebooks, CLI/TUI tools, `vnalpha-service`, and future agent-safe data tools.

```text
vnstock-service  = data platform service
vnalpha-service  = research workspace service
openstock        = umbrella/orchestration repository
```

## Current foundation

The existing direction is already data-only:

- market data collection;
- schema normalization;
- provider comparison and fallback;
- quality validation;
- provider diagnostics;
- broker execution explicitly out of scope.

This design formalizes the service boundary.

---

## Design critique and architectural decisions

### 1. Do not service-wrap legacy dispatch

A service layer must not call legacy provider/explorer paths directly.

Correct path:

```text
HTTP endpoint
→ PluginRuntime
→ PluginRouter
→ ProviderPlugin
→ DatasetContract
→ DataResult
→ serialized response
```

Incorrect path:

```text
HTTP endpoint
→ old explorer/provider class
→ raw DataFrame
→ JSON
```

Reason: direct legacy dispatch would bypass routing diagnostics, provider health, quality metadata, and the new data contracts.

### 2. Phase 3.5 is mandatory before Phase 4

Before service implementation, public supported datasets must route through `PluginRuntime` by default.

The service should be built on one execution boundary only. Supporting both plugin runtime and legacy dispatch inside the service would double the test surface and create inconsistent behavior for `vnalpha-service`.

### 3. The service must return a stable envelope

A raw DataFrame-to-JSON response is not enough for downstream services.

`vnalpha-service` needs:

- data rows;
- provider identity;
- dataset identity;
- quality status;
- diagnostics;
- routing decision;
- timestamps;
- request ID.

Therefore service responses should serialize `DataResult`, not only the underlying DataFrame.

### 4. Authentication must remain command-based

Provider login must be local and interactive:

```bash
vnstock auth login tcbs
vnstock auth status
vnstock auth logout tcbs
vnstock auth delete tcbs
```

The service must not expose REST or MCP login endpoints.

Allowed:

```text
GET /v1/auth/status
GET /v1/auth/providers
```

Forbidden:

```text
POST /v1/auth/login
POST /v1/auth/tcbs/login
POST /v1/auth/token
```

Reason: allowing an HTTP endpoint to receive credentials would turn `vnstock-service` into a broker-login backend and create avoidable security risk.

### 5. Local-first is the default security posture

Default binding should be local-only:

```text
host = 127.0.0.1
port = 6900
public_mode = false
```

If users expose the service beyond localhost, they must explicitly configure that mode and add external security controls.

### 6. JSON is the MVP format; Arrow/Parquet can come later

MVP endpoints should return JSON envelopes.

Later phases may add:

```text
format=json
format=arrow
format=csv
format=parquet
```

Do not block Phase 4 on binary transport.

### 7. Do not duplicate vnalpha responsibilities

`vnstock-service` should answer:

```text
What is the validated market data?
```

It should not answer:

```text
Is this a good setup?
What pattern is this?
Should this symbol be on a watchlist?
What is the backtest result?
```

Those belong to `vnalpha-service`.

---

## Target architecture

```text
HTTP Client / vnalpha-service / Notebook / CLI
        ↓
vnstock-service API
        ↓
Request Parser + Dataset Mapper
        ↓
PluginRuntime
        ↓
DatasetContractRegistry
        ↓
PluginRouter
        ↓
ProviderPlugin
        ↓
Provider client / auth context / fetch
        ↓
Normalizer
        ↓
Quality Validator
        ↓
DataResult
        ↓
JSON response envelope
```

The service layer is intentionally thin. Core behavior stays in:

```text
vnstock/core/runtime
vnstock/core/contracts
vnstock/core/provider
vnstock/core/auth
vnstock/providers
```

---

## Proposed package structure

```text
vnstock/
├── core/
│   ├── runtime/
│   │   ├── plugin_runtime.py
│   │   ├── bootstrap.py
│   │   └── request.py
│   ├── contracts/
│   ├── provider/
│   ├── auth/
│   └── result.py
│
├── service/
│   ├── app.py
│   ├── settings.py
│   ├── dependencies.py
│   ├── schemas.py
│   ├── errors.py
│   ├── serializers.py
│   ├── routes_health.py
│   ├── routes_providers.py
│   ├── routes_auth.py
│   ├── routes_equity.py
│   ├── routes_index.py
│   ├── routes_reference.py
│   ├── routes_fundamental.py
│   └── routes_fund.py
│
├── cli/
│   ├── serve.py
│   └── auth.py
│
├── providers/
│   ├── kbs/
│   ├── vci/
│   ├── dnse/
│   ├── tcbs/
│   ├── fmarket/
│   ├── msn/
│   └── fmp/
│
├── Dockerfile
└── docker-compose.yml
```

---

## Runtime command

```bash
vnstock serve --host 127.0.0.1 --port 6900
```

With config:

```bash
vnstock serve \
  --host 127.0.0.1 \
  --port 6900 \
  --config configs/service.yaml
```

Docker target:

```bash
docker compose up -d vnstock-service
```

---

## API surface v1

### Health and version

```text
GET /healthz
GET /version
```

### Provider metadata

```text
GET /v1/providers
GET /v1/providers/capabilities
GET /v1/providers/health
GET /v1/providers/diagnostics
```

### Auth status

```text
GET /v1/auth/status
GET /v1/auth/providers
```

These endpoints must not expose credential material.

### Equity market data

```text
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/equity/intraday-trades
```

Example:

```text
GET /v1/equity/ohlcv?symbol=FPT&start=2024-01-01&end=2024-06-30&interval=1D&source=auto&validate=true
```

### Index data

```text
GET /v1/index/ohlcv
```

### Reference data

```text
GET /v1/reference/symbols
GET /v1/company/info
```

### Fundamental data

```text
GET /v1/fundamental/balance-sheet
GET /v1/fundamental/income-statement
GET /v1/fundamental/cash-flow
GET /v1/fundamental/financial-ratio
```

### Fund data

```text
GET /v1/fund/nav
GET /v1/fund/holdings
```

---

## Explicitly forbidden endpoints

The service must not expose:

```text
POST /v1/auth/login
POST /v1/auth/tcbs/login
POST /v1/auth/token
GET  /v1/account
GET  /v1/portfolio
POST /v1/order
POST /v1/trade
POST /v1/transfer
POST /v1/margin
POST /v1/portfolio/execute
```

---

## Response envelope

All data endpoints should return a stable envelope.

```json
{
  "data": [
    {
      "symbol": "FPT",
      "time": "2024-01-02",
      "open": 95000,
      "high": 97000,
      "low": 94000,
      "close": 96500,
      "volume": 1234567
    }
  ],
  "meta": {
    "request_id": "req_...",
    "dataset": "equity.ohlcv",
    "symbol": "FPT",
    "interval": "1D",
    "source_requested": "auto",
    "provider": "KBS",
    "quality_status": "PASS",
    "fetched_at": "2026-07-03T00:00:00Z",
    "runtime_path": "plugin_runtime"
  },
  "diagnostics": {
    "routing": {},
    "provider": {},
    "quality": {},
    "warnings": []
  }
}
```

The Python SDK can remain DataFrame-first. The HTTP service should be envelope-first.

---

## Auth design

### Auth commands

```bash
vnstock auth login tcbs
vnstock auth status
vnstock auth logout tcbs
vnstock auth delete tcbs
```

### Auth core

```text
AuthType
AuthSpec
AuthContext
CredentialStore
AuthManager
SessionCache
redaction utilities
auth policies
```

### Credential stores

```text
MemoryCredentialStore       # tests
EnvCredentialStore          # controlled development only
LocalFileCredentialStore    # restricted file permissions
KeyringCredentialStore      # preferred local default where available
VaultCredentialStore        # future enterprise deployment
```

### Auth-aware routing policies

```text
forbid_authenticated
prefer_no_auth
allow_authenticated
require_authenticated
```

Auth-aware routing must combine with health-aware routing.

---

## Configuration

Suggested `configs/service.yaml`:

```yaml
service:
  host: 127.0.0.1
  port: 6900
  public_mode: false
  request_timeout_seconds: 30

runtime:
  default_source: auto
  validate_default: false
  quality_mode: warn
  return_diagnostics: true

routing:
  default_policy: prefer_healthy
  auth_policy: prefer_no_auth
  allow_failing_fallback: false

auth:
  credential_store: keyring
  allow_rest_login: false
  allow_mcp_login: false

cache:
  enabled: true
  backend: sqlite
  path: ./.vnstock/cache.db
```

Defaults should be conservative:

```text
public_mode = false
host = 127.0.0.1
return_diagnostics = true
allow_rest_login = false
allow_mcp_login = false
```

---

## Docker design

### Dockerfile intent

```text
python:3.12-slim
install package
expose 6900
cmd vnstock serve --host 0.0.0.0 --port 6900
```

### docker-compose target

```yaml
services:
  vnstock-service:
    build: .
    container_name: vnstock-service
    ports:
      - "6900:6900"
    environment:
      VNSTOCK_SERVICE_HOST: "0.0.0.0"
      VNSTOCK_SERVICE_PORT: "6900"
      VNSTOCK_QUALITY_ENABLED: "true"
      VNSTOCK_QUALITY_MODE: "warn"
    volumes:
      - vnstock-cache:/home/app/.vnstock
    command: ["vnstock", "serve", "--host", "0.0.0.0", "--port", "6900"]

volumes:
  vnstock-cache:
```

### Interactive login inside container

```bash
docker exec -it vnstock-service vnstock auth login tcbs
docker exec -it vnstock-service vnstock auth status
```

Do not pass username/password through HTTP.

---

## Integration with vnalpha-service

`vnalpha-service` should consume `vnstock-service` through HTTP.

```text
vnalpha-service
→ GET http://vnstock-service:6900/v1/equity/ohlcv
→ receive data + meta + diagnostics
→ store market_ohlcv / canonical_ohlcv / provider_quality_report
```

`vnstock-service` owns market data validity.

`vnalpha-service` owns research interpretation.

---

## Testing strategy

### Unit tests

```text
service schemas
request parsing
response serialization
auth redaction
error mapping
settings loading
```

### Integration tests

```text
GET /healthz
GET /version
GET /v1/providers/capabilities
GET /v1/equity/ohlcv with fake provider
GET /v1/equity/ohlcv source=auto
GET /v1/equity/ohlcv source=KBS
GET /v1/auth/status does not expose secrets
POST /v1/auth/login does not exist
```

### Contract tests for vnalpha-service

`vnalpha-service` expects:

```text
data array
meta.dataset
meta.provider
meta.quality_status
meta.fetched_at
diagnostics.routing
diagnostics.quality
```

### Negative tests

```text
POST /v1/auth/login -> 404 or 405
POST /v1/order -> 404 or 405
GET  /v1/account -> 404 or 405
POST /v1/portfolio/execute -> 404 or 405
```

---

## Phase roadmap

### Phase 3.5 — PluginRuntime completion

```text
PluginRuntime default
public API uses runtime
legacy dispatch retired
DataResult consistent
```

### Phase 4 — Data Service Runtime

```text
FastAPI app
vnstock serve
Dockerfile
docker-compose
read-only data endpoints
auth status endpoints
CLI auth commands
AuthManager/CredentialStore
```

### Phase 5 — Reliable Ingestion Runtime

```text
rate limiter
retry policy
batch request/result envelope
ingestion run tracking
partial failure handling
provider failover
```

### Phase 6 — Storage and Archive

```text
raw archive
normalized archive
Parquet/DuckDB/Postgres sinks
incremental sync metadata
```

### Phase 7 — Data Console, CLI/TUI, and MCP

```text
provider dashboard
capability matrix
data quality viewer
batch monitor
agent-safe MCP data tools
```

---

## Implementation rule

Every service endpoint must be a thin wrapper around `PluginRuntime`.

No endpoint may call provider-specific code directly.

No endpoint may receive credential material.

No endpoint may expose broker, order, account, transfer, margin, portfolio execution, or auto-trading functionality.
