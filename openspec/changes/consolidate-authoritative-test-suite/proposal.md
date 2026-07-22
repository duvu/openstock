## Why

OpenStock needs a compact, locally verifiable set of meaningful `vnalpha`
contracts. Issue #348 is development-only: GitHub Actions and hosted CI are
out of scope and must not be expanded, required or used as closure evidence.

## What Changes

- Keep one authoritative test per public or independently material risk
  contract in a source-aware TOML manifest, with a target of 180–220 and a hard
  cap of 250 exact nodes.
- Provide a 60-second one-contract local loop, local domain selections, and a
  complete local candidate runner that invokes each manifest node once.
- Merge or remove duplicate, superseded, implementation-detail and
  issue-labelled tests while preserving approved financial, point-in-time,
  lineage, transaction, recovery, fail-closed, migration and package risks.
- Reuse isolated migrated DuckDB templates only for compatible current-schema
  contracts; retain dedicated lifecycle inputs where their behavior is owned.
- Correct the manifest, runner dependencies and owning tests as subsequent
  feature work changes source nodes.
- Remove the #348-owned CI path-routing artifacts introduced by the earlier
  snapshot and restore the pre-#349 generic workflow unchanged. The retained
  generic merge-gate policy is not relied upon as #348 evidence.

## Non-goals

- Adding, requiring or observing GitHub Actions, path-aware routing, hosted
  evidence, nightly enforcement or CI expansion. The one-time removal of
  #348-owned routing artifacts is a rollback, not a new CI policy.
- Product behavior, warehouse schema, packaging/release acceptance, broker,
  trading, account or autonomous execution capability changes.

## Impact

- `Makefile`, the manifest validator and `run-test-suite.py` provide local
  selection only.
- `vnalpha` contract tests and `uv.lock` remain consistent with the declared
  development dependencies.
- The active OpenSpec change records local evidence and no hosted-CI dependency.
