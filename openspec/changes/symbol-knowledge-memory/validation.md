# Validation: Symbol Knowledge Memory and Compaction

## Status

```text
OpenSpec authored: yes
Runtime implementation: not started
Validation commands executed: OpenSpec document inspection only
Phase gates: pending
```

This file is the implementation evidence ledger. Do not mark a task or gate complete from PR prose alone. Every completed item must reference code and exact validation output for the tested commit.

## Evidence row format

| UTC timestamp | Commit SHA | Task/gate | Command or inspection | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| pending | pending | OpenSpec review | proposal/design/spec/tasks inspection | pending | Confirm scope, dependencies, and research-only boundary | draft PR |

## Required implementation evidence

### Foundation

- Additive and idempotent migration logs for all supported prior schemas.
- Repository tests for append-only events and lifecycle-safe claims.
- Canonical symbol parsing and path-containment security tests.
- Atomic Markdown write and recovery tests.

### Correctness

- Newer authoritative evidence supersedes stale active knowledge.
- Unsupported numeric claims are rejected.
- Same-authority conflicts remain visible and unresolved.
- User notes remain distinct from verified facts.
- User-authored Markdown regions survive compaction byte-for-byte.
- Historical retrieval excludes future evidence.

### Compaction and scale

- Dry-run proves zero mutation.
- Repeated compaction without new input produces an identical managed hash.
- Archive entries are not duplicated.
- Large event history does not increase configured prompt budget.
- Referenced evidence is not garbage-collected.

### Trust and resilience

- Prompt-injection content inside memory cannot alter classification, planning, policy, tool selection, or approval requirements.
- Corrupt documents are quarantined without blocking unrelated research workflows.
- Concurrent writers do not lose events or corrupt active cards.
- Memory migration failure yields a structured unavailable state rather than a TUI crash.

## Expected validation commands

```bash
make repo-hygiene
make lint-vnalpha
make test-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
```

Focused suites should include symbol-memory models, repositories, migrations, Markdown parsing, lifecycle policy, compaction, retrieval, commands, concurrency, recovery, temporal filtering, and evaluation cases.