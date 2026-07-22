## Context

Issue #348 consolidates the legacy `vnalpha` collection into a bounded local
contract suite. The live issue explicitly supersedes the earlier CI-routing
proposal: no work in this change depends on GitHub Actions or hosted evidence.

## Decisions

### 1. One source-aware TOML inventory owns retained `vnalpha` contracts

`vnalpha/tests/suites/authoritative.toml` records a stable identifier, domain
and exact pytest node for each retained contract. The validator derives test
definitions as `(relative source path, class, method)` tuples, so a matching
name in another file cannot satisfy an inventory entry. It rejects malformed
TOML, invalid paths, duplicate identifiers or nodes, unsupported domains,
missing definitions, unclassified definitions and counts outside 180–220.

### 2. Local commands select one owner, a domain, or a final candidate

`make test-loop TEST=<node>` is the normal 60-second edit-test loop.
`make test-vnalpha-{data,research,application}` resolves one local domain; it
uses `uv run --extra dev` so the declared pytest dependency is installed.
`make test-vnalpha` is reserved for a frozen final candidate and invokes the
complete manifest once.

### 3. The contract budget is maintained by merge or replacement

Every discovered `test_*` definition is either the exact owner in the manifest
or is merged/deleted before validation can pass. Equivalent scenarios share a
single public-boundary test. Distinct financial, point-in-time, transaction,
recovery, migration, package and fail-closed risks retain a dedicated owner.

### 4. CI routing is not part of this change

The prior #348 path classifier and conditional workflow jobs are removed. This
change neither adds nor modifies required CI policy; the existing generic
workflow remains issue #147's concern. Local evidence is sufficient for this
development-only issue.

### 5. Package acceptance remains manual and input-scoped

Packaging/install, dependency-layout, service-unit and release work may use
their manual acceptance commands when those inputs change. Source, test or
OpenSpec work does not select packaging validation under #348.

### 6. Migrated DuckDB setup is isolated and lifecycle coverage stays direct

Compatible tests copy a migrated template into their own temporary warehouse.
Fresh migration, idempotency, upgrade, rollback, crash, reopen, locking and
multiprocessing contracts keep dedicated inputs.

## Risks and mitigations

- A stale or misplaced node fails source-aware manifest validation before
  pytest runs.
- A test-count increase must be offset by a merge or be rejected at the
  220-contract target boundary.
- The developer environment cannot silently omit pytest because local aggregate
  targets declare the `dev` extra.
- No CI routing or hosted-result claim can accidentally become closure evidence.

## Validation and closure

On one frozen local SHA: strictly validate the active OpenSpec, run the bounded
owner test(s) affected by the change, run relevant local domains, then run the
complete authoritative suite once. Record commands and results honestly.
