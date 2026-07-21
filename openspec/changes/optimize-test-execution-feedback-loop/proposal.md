## Why

OpenStock's validation paths repeatedly execute overlapping pytest collections and give every change the cost of broad runtime and packaging checks. The repository needs a spec-driven, measurable test architecture that preserves financial, point-in-time, lineage, transaction, recovery, fail-closed and package correctness while materially shortening local and pull-request feedback.

## What Changes

- Establish an H+1 policy: one canonical happy-path test and one highest-value edge or failure test per public contract, with explicit evidence for additional risk-class exceptions.
- Add machine-checked ownership so every test file belongs to exactly one domain suite, shared-smoke allowlist or migration allowlist.
- Separate consistency/spec, fast smoke, affected-domain, full regression and package/operational acceptance lanes.
- Route pull requests by changed path, fail closed on unknown paths and preserve an always-evaluated required gate whose accepted conclusions are only success or deliberate skip.
- Remove sequential duplicate execution from aggregate Make, verification and CI paths while retaining standalone R0 and R4 developer commands.
- Reuse migrated DuckDB template warehouses through isolated per-test or per-worker copies, retaining dedicated migration, idempotency, upgrade and rollback tests.
- Evaluate `pytest-xdist` only after isolation is proven, retain a sequential rollback switch and keep a sequential nightly lane during observation.
- Consolidate only duplicate, superseded or implementation-detail tests whose retained replacement coverage is recorded; do not weaken approved correctness and safety boundaries.
- Record collection, duration, duplication, migration and environment evidence before and after on exact commits.

Current status: the repository has standalone and aggregate validation targets, a complete pytest suite and required merge-gate infrastructure, but it has no canonical H+1 inventory, checked domain ownership, path-aware runtime routing or measured duplicate-execution control. Issue #348 owns this scheduled change and its acceptance evidence.

Dependencies: existing root Make targets, `openstock-verify`, repository consistency checks, GitHub Actions required-gate behavior and the accepted product/security contracts remain authoritative. This change does not depend on unfinished product capability work, but changes to shared fixtures, migrations, routing or CI must trigger full regression.

Non-goals: reducing tests by an arbitrary percentage; weakening financial or research correctness; masking failures with retries or `continue-on-error`; treating unknown paths as docs-only; changing product behavior; adding broker, trading, account or unrestricted execution capability.

Compatibility and migration: standalone developer targets remain available. Aggregate entry points and CI routing change, but every intentionally skipped lane is explicit and auditable. Parallel execution is opt-in only after repeated sequential/parallel equivalence and can be disabled without changing test semantics.

## Capabilities

### New Capabilities

- `h-plus-one-policy`: Defines contract-level H+1 coverage, approved exception classes, canonical ownership and consolidation evidence.
- `validation-lanes`: Defines local, PR, nightly and release lanes, aggregate deduplication and required-gate conclusions.
- `change-impact-routing`: Defines fail-closed path classification and domain-suite selection for repository changes.
- `duckdb-test-fixtures`: Defines isolated migrated-template reuse, retained migration coverage and controlled parallel execution.

### Modified Capabilities

None.

## Impact

- Root validation and consistency: `Makefile`, repository verification scripts and ownership manifests.
- CI and packaging: `.github/workflows/openstock-ci.yml`, `.github/workflows/vnalpha-debian-package.yml` and the required merge gate.
- Python test infrastructure: `vnalpha/pyproject.toml`, `vnalpha/tests/conftest.py`, domain suite manifests and selected duplicate tests.
- New routing and measurement seams under `scripts/` with focused checker tests.
- OpenSpec registry, artifacts and completion evidence for issue #348.
- No product API or warehouse schema change; research-only boundaries remain unchanged.
