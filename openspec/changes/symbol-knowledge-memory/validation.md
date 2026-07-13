# Validation: Symbol Knowledge Memory and Compaction

## Status

```text
OpenSpec authored: yes
Runtime implementation: complete in the working tree
Validation commands executed: complete; see ledger below
Phase gates: pending implementation-PR evidence attachment (task 11.12)
```

This file is the implementation evidence ledger. Do not mark a task or gate complete from PR prose alone. Every completed item must reference code and exact validation output for the tested commit.

## Evidence row format

| UTC timestamp | Commit SHA | Task/gate | Command or inspection | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-13T09:56:06Z | b834c7c + working tree | Runtime replay corpus | `PYTHONPATH=src uv run python -c '…run_runtime_replay_corpus()…'` | 0 | 22 replay cases passed, including correction, conflict, compaction, temporal-filtering, source-grounding, and injection cases | terminal log |
| 2026-07-13T09:56:06Z | b834c7c + working tree | 11.6 | `make repo-hygiene` | 0 | Repository hygiene passed | terminal log |
| 2026-07-13T09:56:06Z | b834c7c + working tree | 11.7 | `make lint-vnalpha` | 0 | Ruff checks passed; 579 files formatted | terminal log |
| 2026-07-13T09:56:06Z | b834c7c + working tree | 11.8 | `cd vnalpha && uv run pytest -q tests/test_symbol_memory_*.py tests/test_evals_package_resources.py` | 0 | Focused symbol-memory and runtime-resource suite passed | terminal log |
| 2026-07-13T09:56:06Z | b834c7c + working tree | 11.9 | `make test-vnalpha` | 0 | Complete vnalpha pytest suite passed | terminal log |
| 2026-07-13T09:56:06Z | b834c7c + working tree | 11.10 | `make verify-r4` | 0 | R4 regression suite passed | terminal log |
| 2026-07-13T09:56:06Z | b834c7c + working tree | 11.11 | `packaging/scripts/openstock-verify --ci` | 0 | 16 OK, 1 expected systemd warning, 0 failures | terminal log |
| 2026-07-13T09:56:06Z | b834c7c + working tree | Manual CLI QA | `vnalpha --help`; isolated `/memory status`; invalid `/memory compact` | 0 / 0 / 1 | Help and status succeeded; invalid compact showed the documented usage error | terminal log |
| 2026-07-13T10:52:07Z | working tree | Runtime memory evaluation | `cd vnalpha && uv run vnalpha eval symbol-memory-runtime --ci` | 0 | correction, conflict, compaction, temporal filtering, and source grounding all passed | terminal log |
| 2026-07-13T10:52:07Z | working tree | Strict OpenSpec validation | `openspec validate symbol-knowledge-memory --strict` | 0 | Change is valid | terminal log |
| 2026-07-13T10:52:07Z | working tree | 11.6 | `make repo-hygiene` | 0 | Repository hygiene passed | terminal log |
| 2026-07-13T10:52:07Z | working tree | 11.7 | `make lint-vnalpha` | 0 | Ruff checks passed; 582 files formatted | terminal log |
| 2026-07-13T10:52:07Z | working tree | 11.9 | `make test-vnalpha` | 0 | Complete vnalpha pytest suite passed | terminal log |
| 2026-07-13T10:52:07Z | working tree | 11.10 | `make verify-r4` | 0 | R4 regression suite passed | terminal log |
| 2026-07-13T10:52:07Z | working tree | 11.11 | `packaging/scripts/openstock-verify --ci` | 0 | 16 OK, 1 expected systemd warning, 0 failures | terminal log |

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
