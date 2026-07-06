# Change Proposal: Phase 4 — Auth-aware Local Data Service

## Change ID

`phase-4-auth-aware-local-data-service`

## Summary

Turn `vnstock` into a local, Docker-ready data service while keeping authentication as command-based, interactive, and data-read only.

This phase introduces:

- local `vnstock serve` runtime;
- Docker-ready service packaging;
- command-based provider login such as `vnstock auth login tcbs`;
- centralized auth manager;
- credential store abstraction;
- auth-aware provider routing;
- auth status endpoint;
- no REST login endpoint;
- no MCP login tool;
- no account, order, portfolio, transfer, or trading execution capability.

The goal is to support credentialed data providers safely without turning `vnstock` into a broker-login backend.

## Motivation

Earlier phases establish the data platform foundation:

- Phase 1: dataset contracts, provider plugin interface, provider registry, router skeleton, and `DataResult`.
- Phase 2: normalized internal provider plugins.
- Phase 3: health-aware routing and provider diagnostics.

Phase 4 adds a service runtime and auth layer so that users can run `vnstock` as a local service and log in through CLI commands when a provider requires credentials.

Current TCBS login logic exists as provider-specific code. Phase 4 should migrate this pattern into a central auth architecture and remove provider-specific credential handling from the data fetch path.

## Goals

### G1. Add local data service runtime

Add a local service command:

```bash
vnstock serve --host 127.0.0.1 --port 6900
```

The service should expose data-read endpoints only.

### G2. Add Docker-ready runtime

Add Docker packaging for local/single-user usage.

The default service binding should be local-only unless explicitly configured otherwise.

### G3. Add command-based login

Add CLI commands:

```bash
vnstock auth login tcbs
vnstock auth status
vnstock auth logout tcbs
vnstock auth delete tcbs
```

Login must be interactive and local. The service must not expose a public login endpoint.

### G4. Add centralized auth core

Create a central auth layer for provider credentials:

- `AuthType`
- `AuthSpec`
- `AuthContext`
- `CredentialStore`
- `AuthManager`
- `SessionCache`
- redaction utilities
- auth policies

### G5. Add credential store abstraction

Credential storage must be centralized and provider-independent.

Initial stores:

- memory store for tests;
- environment-backed store for controlled development use;
- local file store with restricted permissions;
- keyring store where available;
- vault-compatible interface for future enterprise deployments.

### G6. Add auth-aware routing

Provider routing should consider auth policy:

- `forbid_authenticated`
- `prefer_no_auth`
- `allow_authenticated`
- `require_authenticated`

Auth-aware routing must combine with Phase 3 health-aware routing.

### G7. Add auth status endpoint

The service may expose safe auth status:

```text
GET /v1/auth/status
GET /v1/auth/providers
```

These endpoints must not expose credential material.

### G8. Keep data-only boundary

Authenticated providers may be used only for market, reference, fundamental, and fund data read use cases.

## Non-goals

This phase does not implement:

- REST login endpoint;
- MCP login tool;
- multi-user credential service;
- user account management;
- broker account APIs;
- order placement;
- transfer operations;
- margin operations;
- portfolio management;
- trading signals;
- stock recommendations;
- public internet deployment.

## Scope

### In scope

```text
vnstock/core/auth/
vnstock/service/
vnstock/cli/auth.py
Dockerfile
docker-compose.yml
docs/AUTH_AND_CREDENTIALS.md
docs/LOCAL_DATA_SERVICE.md
docs/DOCKER_RUNTIME.md
tests/unit/core/auth/
tests/unit/service/
```

### Out of scope

```text
vnstock/mcp/login tools
broker/account/order endpoints
multi-user identity/RBAC
production internet-facing deployment
```

## Service endpoint scope

Allowed endpoints:

```text
GET /healthz
GET /v1/providers
GET /v1/providers/health
GET /v1/providers/capabilities
GET /v1/auth/status
GET /v1/auth/providers
GET /v1/equity/ohlcv
GET /v1/equity/quote
GET /v1/index/ohlcv
GET /v1/company/info
GET /v1/fundamental/balance-sheet
GET /v1/fund/nav
```

Forbidden endpoints:

```text
POST /v1/auth/login
POST /v1/order
GET /v1/account
GET /v1/portfolio
POST /v1/transfer
POST /v1/margin
```

## Success criteria

Phase 4 is complete when:

- `vnstock serve` starts a local data service;
- Docker runtime exists for local single-user service;
- `vnstock auth login tcbs` works as an interactive command;
- auth state is stored through `CredentialStore`;
- provider plugins declare `auth_spec(dataset)`;
- router supports auth policies;
- service exposes data-read endpoints only;
- service exposes safe auth status only;
- REST login endpoint is absent;
- MCP login tool is absent;
- sensitive credential material is not printed or returned;
- TCBS login is explicit, experimental, and not used by default auto-routing;
- backward-compatible SDK calls remain intact.

## Validation commands

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```
