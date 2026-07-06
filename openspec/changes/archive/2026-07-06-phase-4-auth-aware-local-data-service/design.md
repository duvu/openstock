# Design: Phase 4 — Auth-aware Local Data Service

## Overview

Phase 4 turns `vnstock` into a local, Docker-ready data service while keeping provider login command-based and interactive.

The design avoids a login server. Users authenticate with CLI commands, then the local service reads auth state through a centralized credential store.

## Architecture

```text
User CLI
  -> vnstock auth login PROVIDER
  -> AuthManager
  -> CredentialStore

User / vnalpha / notebook / local client
  -> vnstock service HTTP data endpoint
  -> ProviderRouter
  -> AuthManager
  -> ProviderPlugin
  -> DataResult
```

## Key boundary

Phase 4 service exposes data-read APIs only.

Login must happen through local command execution, not through REST or MCP.

## Components

### Auth core

Suggested modules:

```text
vnstock/core/auth/types.py
vnstock/core/auth/spec.py
vnstock/core/auth/context.py
vnstock/core/auth/credential_store.py
vnstock/core/auth/manager.py
vnstock/core/auth/session_cache.py
vnstock/core/auth/redaction.py
vnstock/core/auth/policies.py
```

Auth core should define:

- auth type;
- auth spec;
- auth context;
- credential store interface;
- auth manager;
- session cache;
- redaction utility;
- auth policy.

### Provider auth spec

Provider plugins should expose `auth_spec(dataset)`.

A provider may declare:

- no auth required;
- optional auth;
- required auth;
- interactive local login required.

TCBS should be treated as experimental and explicit-only until provider terms and stability are clear.

### Credential store

Credential storage must be centralized.

Initial implementations:

- memory store for tests;
- environment-backed store for controlled development;
- restricted local file store;
- keyring store where available;
- vault-compatible adapter interface for future server mode.

No provider should read or write auth state independently once Phase 4 is implemented.

### CLI auth commands

Target commands:

```bash
vnstock auth login tcbs
vnstock auth status
vnstock auth logout tcbs
vnstock auth delete tcbs
```

The command should be interactive. It may ask for provider account information and OTP locally, but it must not print sensitive material after login.

### Local data service

Target command:

```bash
vnstock serve --host 127.0.0.1 --port 6900
```

Default host should be local-only.

The service should be suitable for:

- local developer workstation;
- local Docker runtime;
- trusted single-user machine;
- integration with `vnalpha` in local/service mode.

It is not a multi-user credential platform.

### Docker runtime

Docker packaging should include:

- Dockerfile;
- docker-compose example;
- mounted data/auth volume;
- local-only default port binding;
- clear docs for interactive auth inside container.

Example workflow:

```bash
docker compose up -d vnstock-service
docker exec -it vnstock-service vnstock auth login tcbs
docker exec -it vnstock-service vnstock auth status
```

## Auth policy

Supported policies:

```text
forbid_authenticated
prefer_no_auth
allow_authenticated
require_authenticated
```

Default for service should be `prefer_no_auth`.

Authenticated providers should not be selected automatically unless policy allows it and auth state exists.

## Service endpoints

Allowed endpoint groups:

- health endpoint;
- provider metadata;
- provider health;
- provider capability matrix;
- safe auth status;
- market data read;
- reference data read;
- fundamental data read;
- fund data read.

Forbidden endpoint groups:

- provider login over HTTP;
- account data;
- portfolio data;
- order placement;
- transfer;
- margin;
- trading recommendation.

## TCBS migration

Existing TCBS auth code should be migrated behind AuthManager.

Required changes:

- mark TCBS auth as experimental;
- use centralized credential store;
- avoid printing credential material;
- avoid exposing provider session details in user-facing errors;
- restrict use to local CLI and local SDK/service;
- do not enable authenticated TCBS provider in default auto-routing.

## DataResult integration

DataResult diagnostics may include safe auth metadata:

- whether auth was used;
- auth type;
- provider;
- scopes or data-read intent;
- expiry if known;
- credential reference label.

Diagnostics must not include credential material.

## Test strategy

Tests should cover:

- auth spec model;
- credential store interface;
- auth manager behavior;
- auth policy routing;
- CLI command behavior with mocks;
- service endpoint scope;
- Docker command documentation examples;
- absence of forbidden endpoints;
- safe diagnostics behavior.

## Migration strategy

1. Add auth core contracts.
2. Add credential stores.
3. Wrap existing TCBS auth behind AuthManager.
4. Add CLI auth commands.
5. Add local data service.
6. Add Docker runtime.
7. Add auth-aware routing.
8. Add service endpoint tests.
9. Document local-only and data-only constraints.

## Open questions

1. Which credential store should be default for local Docker?
2. Should local file store be encrypted in Phase 4 or restricted-permission only?
3. Should service support writeable auth volume by default?
4. Should `vnstock serve` be installed as a project script immediately?
5. Should TCBS authenticated data be explicit-source only for the first release?
