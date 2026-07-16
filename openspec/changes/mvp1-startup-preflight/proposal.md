## Why

OpenStock has an installed-host verifier (`openstock-verify`), a canonical
Compose service, a warehouse migrator, transaction-safe backup/restore (#150)
and a typed LLM preflight (#165), but no single documented command to bring the
MVP1 chat vertical slice up on a clean Linux host, and no curated read-only
preflight that verifies exactly the dependencies the chat slice needs.

Issue #166 provides one documented, idempotent startup path and an installed-host
MVP1 preflight suitable for CI and operators.

## What Changes

- add `openstock-mvp1-start`: one idempotent command that validates/creates the
  persistent warehouse, knowledge and log directories with safe permissions,
  verifies or starts `vnstock-service` and waits (bounded) for health, migrates
  the warehouse (`vnalpha init`, never overwriting valid data), runs the MVP1
  preflight, then launches the TUI or (`--no-launch`) prints the exact launch
  command;
- add `openstock-verify --mvp1`: a read-only MVP1 preflight composing service
  health/version, warehouse path/writable/free-disk, warehouse-migration
  readiness, knowledge path readiness, the #165 LLM route preflight,
  backup/restore command availability (#150) and release/commit metadata, with
  PASS/WARN/FAIL diagnostics and non-zero exit on blockers; honours `--ci` to
  stay offline;
- keep Compose, systemd, `.env.example`, README and the operator runbook
  consistent; register the new script in the verify syntax check;
- add packaging tests: `openstock-verify --mvp1 --ci` exits 0 with no `[FAIL]`,
  `openstock-mvp1-start` help/rejection, and an idempotent-startup fixture test
  against fake binaries.

## Capabilities

### Added Capabilities

- `mvp1-startup-preflight`: one-command idempotent MVP1 startup and a read-only
  installed-host MVP1 preflight for the chat vertical slice.

## Impact

- new `packaging/scripts/openstock-mvp1-start`; `--mvp1` mode and MVP1 checks in
  `packaging/scripts/openstock-verify`; `mvp1-start`/`verify-mvp1` Makefile
  targets;
- docs in `README.md` and `packaging/docs/OPERATOR.md`;
- tests in `packaging/tests/test_verify_helpers.sh` and
  `packaging/test/test_mvp1_start.sh`;
- No service is exposed publicly by default. Startup is idempotent and never
  overwrites existing valid data or credentials. The read-only research boundary
  remains intact.
