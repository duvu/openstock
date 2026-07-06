# Spec: Auth-aware Local Data Service

## ADDED Requirements

### Requirement: Local data service runtime

`vnstock` SHALL provide a local data service runtime.

The service SHALL be started by a command equivalent to:

```bash
vnstock serve --host 127.0.0.1 --port 6900
```

The default binding SHOULD be local-only.

#### Scenario: service starts locally

Given the service command is executed with default options
When startup succeeds
Then the service SHALL listen on a local interface and expose a health endpoint.

#### Scenario: service remains data-read only

Given the service is running
When endpoints are inspected
Then the service SHALL expose data-read endpoints only.

---

### Requirement: Docker-ready runtime

`vnstock` SHALL provide Docker-ready runtime artifacts for local/single-user operation.

Docker artifacts SHOULD include:

- Dockerfile;
- docker-compose example;
- service healthcheck;
- mounted data/auth volume;
- local-only default port binding.

#### Scenario: Docker service supports interactive command login

Given the Docker service is running
When the user executes an interactive auth command inside the container
Then the command SHALL use the configured credential store and the service SHALL be able to read auth state afterward.

---

### Requirement: Command-based provider login

`vnstock` SHALL support command-based provider login.

Supported commands SHOULD include:

```bash
vnstock auth login PROVIDER
vnstock auth status
vnstock auth logout PROVIDER
vnstock auth delete PROVIDER
```

Login SHALL be local and interactive.

#### Scenario: TCBS command login

Given the user runs `vnstock auth login tcbs`
When the provider requires interactive verification
Then the command SHALL complete the local interactive flow and store auth state through `CredentialStore`.

#### Scenario: login does not print credential material

Given provider login succeeds or fails
When CLI output is produced
Then the CLI SHALL NOT print sensitive credential material.

---

### Requirement: No REST login endpoint

The local data service SHALL NOT expose a REST login endpoint.

#### Scenario: login endpoint is absent

Given the service is running
When the caller attempts to find or call a provider login endpoint
Then no such endpoint SHALL be available.

---

### Requirement: Centralized auth core

`vnstock` SHALL provide centralized auth components.

The auth core SHALL include:

- auth type;
- auth spec;
- auth context;
- credential store interface;
- auth manager;
- session cache abstraction;
- redaction utility;
- auth policy.

#### Scenario: provider declares auth spec

Given a provider plugin supports authenticated data access
When `auth_spec(dataset)` is called
Then the provider SHALL return its auth requirements for that dataset.

#### Scenario: public provider declares no-auth spec

Given a provider does not require authentication for a dataset
When `auth_spec(dataset)` is called
Then the provider SHALL declare that no auth is required.

---

### Requirement: Credential store abstraction

`vnstock` SHALL centralize credential storage behind `CredentialStore`.

Initial implementations SHOULD include:

- memory store for tests;
- environment-backed store for controlled development;
- restricted local file store;
- keyring store where supported;
- vault-compatible adapter interface for future deployments.

#### Scenario: provider does not access credential storage directly

Given a provider needs auth state
When it prepares a request
Then it SHALL obtain auth context through `AuthManager` rather than provider-specific storage logic.

#### Scenario: missing credential is handled safely

Given a provider requires auth state and none exists
When a data request is routed to that provider
Then the platform SHALL fail clearly or select another provider according to auth policy.

---

### Requirement: Auth-aware routing

`ProviderRouter` SHALL support auth policies.

Supported policies SHALL include:

```text
forbid_authenticated
prefer_no_auth
allow_authenticated
require_authenticated
```

Auth-aware routing SHALL combine with provider capability and health-aware routing.

#### Scenario: forbid authenticated providers

Given a dataset has public and authenticated providers
When auth policy is `forbid_authenticated`
Then the router SHALL not select authenticated providers.

#### Scenario: prefer no-auth providers

Given a public provider is available
When auth policy is `prefer_no_auth`
Then the router SHOULD select the public provider unless policy or source forces otherwise.

#### Scenario: allow authenticated provider

Given an authenticated provider has valid auth state
When auth policy is `allow_authenticated`
Then the router MAY select that provider according to health and priority.

#### Scenario: require authenticated provider

Given auth policy is `require_authenticated`
When no authenticated provider has valid auth state
Then routing SHALL fail clearly.

---

### Requirement: Safe auth status endpoint

The service MAY expose safe auth status endpoints.

Allowed status endpoints:

```text
GET /v1/auth/status
GET /v1/auth/providers
```

These endpoints SHALL NOT expose credential material.

#### Scenario: auth status is safe

Given the service returns auth status
When the response is inspected
Then it SHALL include only safe metadata such as provider, availability, and expiry where known.

---

### Requirement: Forbidden endpoint groups

The service SHALL NOT expose broker or trading endpoints.

Forbidden endpoint groups include:

- provider login over HTTP;
- account data;
- portfolio data;
- order placement;
- transfer;
- margin;
- trading recommendation.

#### Scenario: order endpoint absent

Given the service is running
When route definitions are inspected
Then order placement endpoints SHALL be absent.

#### Scenario: account endpoint absent

Given the service is running
When route definitions are inspected
Then account and portfolio endpoints SHALL be absent.

---

### Requirement: TCBS authenticated mode is experimental and explicit

TCBS authenticated mode SHALL be treated as experimental and explicit-only.

#### Scenario: TCBS is not selected by default solely because auth exists

Given TCBS auth state exists
When the user requests data with default routing policy
Then TCBS authenticated mode SHALL NOT be selected solely because auth exists.

#### Scenario: explicit TCBS source may use auth state

Given TCBS auth state exists
When the user requests `source="TCBS"` with an auth policy that allows authenticated providers
Then the provider MAY use TCBS auth state for data-read requests.

---

### Requirement: DataResult safe auth diagnostics

`DataResult` diagnostics MAY include safe auth metadata.

Safe metadata may include:

- whether auth was used;
- auth type;
- provider;
- data-read intent;
- expiry if known;
- credential reference label.

Diagnostics SHALL NOT include credential material.

#### Scenario: DataFrame attrs remain safe

Given a public API returns a `DataFrame`
When auth metadata is attached to `DataFrame.attrs`
Then the metadata SHALL include only safe auth diagnostics.

---

### Requirement: Backward-compatible SDK behavior

Phase 4 SHALL preserve existing SDK usage.

#### Scenario: public data request remains compatible

Given a user calls a public no-auth data request
When Phase 4 auth infrastructure exists
Then the request SHALL continue to work without requiring login.

#### Scenario: service mode is optional

Given a user imports and uses `vnstock` as a Python SDK
When no service is running
Then SDK usage SHALL remain available.
