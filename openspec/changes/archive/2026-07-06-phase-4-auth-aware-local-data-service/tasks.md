# Tasks: Phase 4 — Auth-aware Local Data Service

## 0. Prerequisite check

- [x] Confirm Phase 1 platform contracts exist.
- [x] Confirm Phase 2 provider plugins exist.
- [x] Confirm Phase 3 health-aware routing exists or is planned as a prerequisite.
- [x] Confirm TCBS legacy auth code is inventoried.
- [x] Confirm service scope remains data-read only.

## 1. Auth core

- [x] Create `vnstock/core/auth/`.
- [x] Add auth type model.
- [x] Add auth spec model.
- [x] Add auth context model.
- [x] Add auth policy model.
- [x] Add session cache abstraction.
- [x] Add safe diagnostics metadata model.
- [x] Add redaction helper.
- [x] Add tests for each auth model.

## 2. Credential store

- [x] Add `CredentialStore` interface.
- [x] Add memory credential store for tests.
- [x] Add environment-backed credential store for controlled development use.
- [x] Add restricted local file credential store.
- [x] Add keyring credential store where supported.
- [x] Add vault-compatible interface for future enterprise deployments.
- [x] Add tests for read/write/delete behavior.
- [x] Add tests for missing credential behavior.
- [x] Add tests for safe diagnostics output.

## 3. Auth manager

- [x] Add `AuthManager`.
- [x] Implement provider auth context resolution.
- [x] Implement provider login dispatch.
- [x] Implement provider logout.
- [x] Implement auth status.
- [x] Implement credential availability checks.
- [x] Ensure AuthManager does not expose raw credential material to callers.
- [x] Add tests for login/status/logout flows using mocked providers.

## 4. Provider auth spec

- [x] Add `auth_spec(dataset)` to provider plugin contract.
- [x] Add no-auth spec for public providers.
- [x] Add optional/experimental auth spec for TCBS.
- [x] Mark TCBS authenticated mode as explicit-only.
- [x] Ensure account, order, transfer, margin, and portfolio capabilities are out of scope.
- [x] Add tests for provider auth spec declarations.

## 5. TCBS auth migration

- [x] Wrap existing TCBS auth behind AuthManager.
- [x] Preserve command-based manual login behavior.
- [x] Remove provider-side direct auth state access where possible.
- [x] Stop printing credential material when saving fails.
- [x] Avoid exposing provider session details in user-facing errors.
- [x] Store auth state through CredentialStore.
- [x] Add tests for OTP-required flow with mocks.
- [x] Add tests for failed login with safe error handling.
- [x] Add tests that TCBS auth remains data-read only.

## 6. CLI auth commands

- [x] Add `vnstock auth login PROVIDER`.
- [x] Add `vnstock auth status`.
- [x] Add `vnstock auth logout PROVIDER`.
- [x] Add `vnstock auth delete PROVIDER`.
- [x] Keep login interactive and local.
- [x] Ensure CLI does not print sensitive credential material.
- [x] Add CLI tests with mocked input/output.
- [x] Keep legacy `vnstock-tcbs-login` as a compatibility shim or document deprecation.

## 7. Auth-aware routing

- [x] Add auth policy handling to ProviderRouter.
- [x] Support `forbid_authenticated`.
- [x] Support `prefer_no_auth`.
- [x] Support `allow_authenticated`.
- [x] Support `require_authenticated`.
- [x] Combine auth policy with provider health policy.
- [x] Ensure authenticated providers are not selected by default unless policy allows.
- [x] Add tests for each auth policy.

## 8. Local data service

- [x] Create `vnstock/service/`.
- [x] Add service app entrypoint.
- [x] Add `vnstock serve` command.
- [x] Add health endpoint.
- [x] Add provider metadata endpoints.
- [x] Add provider health endpoint.
- [x] Add provider capabilities endpoint.
- [x] Add safe auth status endpoint.
- [x] Add data-read endpoints for market/reference/fundamental/fund datasets.
- [x] Ensure service has no login endpoint.
- [x] Ensure service has no account/order/portfolio endpoints.
- [x] Add service tests.

## 9. Docker runtime

- [x] Add Dockerfile.
- [x] Add docker-compose example.
- [x] Add local-only default binding.
- [x] Add mounted auth/data volume.
- [x] Add interactive login documentation for Docker.
- [x] Add service healthcheck.
- [x] Document single-user local scope.
- [x] Document that public internet deployment is out of scope.

## 10. DataResult integration

- [x] Attach safe auth metadata to `DataResult.diagnostics`.
- [x] Attach safe auth metadata to `DataFrame.attrs` where appropriate.
- [x] Preserve existing quality metadata.
- [x] Add tests for safe auth diagnostics.
- [x] Add tests for backward compatibility.

## 11. Endpoint allowlist and denylist

- [x] Define allowed service endpoints.
- [x] Define forbidden endpoint groups.
- [x] Add tests that forbidden endpoints are absent.
- [x] Add tests that service remains data-read only.

## 12. Documentation

- [x] Add `docs/AUTH_AND_CREDENTIALS.md`.
- [x] Add `docs/LOCAL_DATA_SERVICE.md`.
- [x] Add `docs/DOCKER_RUNTIME.md`.
- [x] Document CLI auth workflow.
- [x] Document Docker auth workflow.
- [x] Document local-only service assumptions.
- [x] Document TCBS experimental status.
- [x] Document data-only boundary.
- [x] Document forbidden APIs.

## 13. Validation

Run:

```bash
ruff check .
ruff format --check .
PYTHONPATH=. pytest tests/unit/core tests/unit/service tests/contracts -q
python -m build --sdist --wheel --no-isolation
```

## Completion checklist

Phase 4 is complete when:

- [x] auth core exists;
- [x] credential store abstraction exists;
- [x] AuthManager exists;
- [x] TCBS auth is wrapped behind AuthManager;
- [x] CLI auth commands exist;
- [x] auth-aware routing exists;
- [x] local data service exists;
- [x] Docker runtime exists;
- [x] no REST login endpoint exists;
- [x] no account/order/portfolio endpoints exist;
- [x] service is local/single-user by default;
- [x] tests pass;
- [x] docs are updated.
