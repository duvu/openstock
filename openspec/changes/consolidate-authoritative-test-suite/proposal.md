## Why

OpenStock's validation paths repeatedly execute overlapping pytest collections and give every change the cost of broad runtime and packaging checks. The repository needs a spec-driven, measurable test architecture that preserves financial, point-in-time, lineage, transaction, recovery, fail-closed and package correctness while materially shortening local and pull-request feedback.

## What Changes

- Establish one authoritative test per public or approved risk contract, using a table-driven H+1 case only where it represents the same contract.
- Replace the broad file inventory with a compact authoritative manifest of approximately 180–220 tests and a hard consistency cap of 250.
- Separate consistency/spec, fast smoke, affected-domain, full regression and package/operational acceptance lanes.
- Route pull requests by changed path, fail closed on unknown paths and preserve an always-evaluated required gate whose accepted conclusions are only success or deliberate skip.
- Remove sequential duplicate execution from aggregate Make, verification and CI paths while retaining standalone R0 and R4 developer commands.
- Reuse migrated DuckDB template warehouses through isolated per-test or per-worker copies, retaining dedicated migration, idempotency, upgrade and rollback tests.
- Evaluate `pytest-xdist` only after isolation is proven, retain a sequential rollback switch and keep a sequential nightly lane during observation.
- Delete or merge duplicate, superseded, issue-number and implementation-detail tests; do not weaken approved correctness and safety boundaries.
- Record collection, duration, duplication, migration and environment evidence before and after on exact commits.

Current status: initial aggregate de-duplication, routing, a file-level inventory and fixture reuse have landed, but the repository still has thousands of collected tests rather than the required authoritative budget. Issue #348 owns the replacement inventory, consolidation and acceptance evidence.

Dependencies: existing root Make targets, `openstock-verify`, repository consistency checks, GitHub Actions required-gate behavior and the accepted product/security contracts remain authoritative. This change does not depend on unfinished product capability work, but changes to shared fixtures, migrations, routing or CI must trigger full regression.

Non-goals: weakening financial or research correctness; masking failures with retries or `continue-on-error`; treating unknown paths as docs-only; changing product behavior; adding broker, trading, account or unrestricted execution capability.

Compatibility and migration: standalone developer targets remain available. Aggregate entry points and CI routing change, but every intentionally skipped lane is explicit and auditable. Parallel execution is opt-in only after repeated sequential/parallel equivalence and can be disabled without changing test semantics.

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
- Python test infrastructure: `vnalpha/pyproject.toml`, `vnalpha/tests/conftest.py`, domain suite manifests and selected duplicate tests.
- New routing and measurement seams under `scripts/` with focused checker tests.
- OpenSpec registry, artifacts and completion evidence for issue #348.
- No product API or warehouse schema change; research-only boundaries remain unchanged.
