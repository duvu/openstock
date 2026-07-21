## Why

OpenStock's validation paths repeatedly execute overlapping pytest collections and give every change the cost of broad runtime and packaging checks. The repository needs a spec-driven, measurable test architecture that preserves financial, point-in-time, lineage, transaction, recovery, fail-closed and package correctness while materially shortening local and pull-request feedback.

## What Changes

- Establish one authoritative test per public or approved risk contract; parameterization is allowed only where it is the same contract.
- Replace the broad file inventory with a compact authoritative manifest of approximately 180–220 tests and a hard consistency cap of 250.
- Separate consistency/spec, the 60-second one-contract development loop, affected-domain, full regression and package/operational acceptance lanes.
- Route pull requests by changed path, fail closed on unknown paths and preserve an always-evaluated required gate whose accepted conclusions are only success or deliberate skip.
- Delete obsolete R0/R4/Phase and duplicate checker wrappers rather than retaining them as hidden lanes.
- Reuse migrated DuckDB template warehouses through isolated per-test or per-worker copies, retaining dedicated migration, idempotency, upgrade and rollback tests.
- Delete or merge duplicate, superseded, issue-number and implementation-detail tests; do not weaken approved correctness and safety boundaries.
- Record collection, duration, duplication, migration and environment evidence before and after on exact commits.

Current status: initial aggregate de-duplication, routing, a file-level inventory and fixture reuse have landed, but the repository still has thousands of collected tests rather than the required authoritative budget. Issue #348 owns the replacement inventory, consolidation and acceptance evidence.

Dependencies: existing root Make targets, `openstock-verify`, repository consistency checks, GitHub Actions required-gate behavior and the accepted product/security contracts remain authoritative. Ordinary `vnalpha/src/**` changes select compact relevant domains, not Debian acceptance.

Non-goals: weakening financial or research correctness; masking failures with retries or `continue-on-error`; treating unknown paths as docs-only; changing product behavior; adding broker, trading, account or unrestricted execution capability.

Compatibility and migration: `make test-loop` remains the normal local command. Aggregate entry points and CI routing change, but every intentionally skipped lane is explicit and auditable.

## Capabilities

### New Capabilities

- `one-to-one-test-policy`: Defines one authoritative public/risk contract owner, H+1 case selection and consolidation evidence.
- `sixty-second-development-loop`: Defines the bounded local development command and prohibited broad inner-loop gates.
- `authoritative-test-budget`: Defines the 180–220 target and hard cap of 250.
- `test-and-check-inventory`: Defines KEEP/MERGE/REPLACE/DELETE decisions for tests and validation checks.
- `validation-lanes`: Defines local, PR, nightly and release lanes, aggregate deduplication and required-gate conclusions.
- `duckdb-fixture-efficiency`: Defines isolated migrated-template reuse, retained migration coverage and controlled parallel execution.

### Modified Capabilities

None.

## Impact

- Root validation and consistency: `Makefile`, repository verification scripts and ownership manifests.
- CI and packaging: `.github/workflows/openstock-ci.yml`, `.github/workflows/vnalpha-debian-package.yml` and the required merge gate.
- Python test infrastructure: `vnalpha/pyproject.toml`, `vnalpha/tests/conftest.py`, the authoritative contract inventory and selected duplicate tests.
- One small inventory parser/checker under `scripts/`.
- OpenSpec registry, artifacts and completion evidence for issue #348.
- No product API or warehouse schema change; research-only boundaries remain unchanged.
