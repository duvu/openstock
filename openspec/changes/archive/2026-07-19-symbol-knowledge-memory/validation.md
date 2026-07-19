# Validation: Symbol Knowledge Memory and Compaction

Final implementation SHA: `e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d`

| UTC timestamp | Commit SHA | Task/gate | Command or inspection | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 0.1–0.6, 1.1–1.7, 2.1–2.8, 3.1–3.9, 4.1–4.9, 5.1–5.10, 6.1–6.10, 7.1–7.9, 8.1–8.10, 9.1–9.6, 10.1–10.12, 11.1–11.12, 12.1–12.6 | `make repo-hygiene` | 0 | Repository hygiene and the complete memory task/evidence matrix passed on the exact candidate | PR #247 and exact-candidate command transcript |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 11.7 | `make lint-vnalpha` | 0 | Ruff checks and formatting passed | exact-candidate command transcript |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 11.9 | `make test-vnalpha` | 0 | Complete vnalpha suite passed | exact-candidate command transcript and PR #247 CI |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 11.10 | `make verify-r4` | 0 | R4 regression suite passed | exact-candidate command transcript |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 11.11 | `packaging/scripts/openstock-verify --ci` | 0 | Repository and package verification passed with no blocking failure | exact-candidate command transcript |

## Status

```text
OpenSpec authored: yes
Runtime implementation: complete at commit 3af296419b04155e4aee16d45258f6d458fd8ba2
Validation commands executed: complete on the exact implementation commit; see ledger below
Phase gates: G1-G5 passed; exact evidence attached to draft implementation PR #71
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
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | Validation environment | `cd vnalpha && UV_CACHE_DIR=/tmp/openstock-uv-cache uv sync --extra dev --frozen`; bootstrap `pip` into the isolated virtual environment for wheel tests | 0 | Locked development environment created with Python 3.13.5 and pytest 9.1.1 | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | G1 | `cd vnalpha && uv run pytest -q tests/test_symbol_memory_models.py tests/test_symbol_memory_repository.py tests/test_symbol_memory_markdown.py tests/test_symbol_memory_ingestion.py tests/test_symbol_memory_availability.py tests/test_symbol_memory_boundaries.py` | 0 | 35 focused foundation, migration, path, availability, boundary, and user-note tests passed | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | G2 | `cd vnalpha && uv run pytest -q tests/test_symbol_memory_lifecycle.py tests/test_symbol_memory_ingestion.py tests/test_symbol_memory_retrieval.py` | 0 | 21 authority, correction, conflict, numeric-grounding, and temporal-lifecycle tests passed | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | G3 | `cd vnalpha && uv run pytest -q tests/test_symbol_memory_compaction.py tests/test_symbol_memory_maintenance.py tests/test_symbol_memory_locking.py tests/test_symbol_memory_recovery.py` | 0 | 19 compaction, archive, atomicity, concurrency, and recovery tests passed | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | G4 | `cd vnalpha && uv run pytest -q tests/test_symbol_memory_retrieval.py tests/test_symbol_memory_maintenance.py tests/test_symbol_memory_assistant_context.py tests/test_symbol_memory_runtime_evaluation.py tests/test_evals_package_resources.py` | 0 | 16 retrieval-budget, no-lookahead, context-trust, runtime-corpus, and package-resource tests passed | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | G4 runtime replay | `cd vnalpha && VNALPHA_LOG_ROOT=/tmp/openstock-state/logs uv run vnalpha eval symbol-memory-runtime --ci` | 0 | correction, conflict, compaction, temporal filtering, and source grounding all passed | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | Manual command QA | isolated command-registry driver for `/memory status`, `remember`, `show`, `compact FPT --dry-run`, and missing-symbol `/memory compact`; `uv run vnalpha --help` | 0 | Happy paths created and read `FPT.md`; dry-run preview succeeded; invalid input returned the documented usage error; CLI help rendered | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | 11.6, G5 | `make repo-hygiene` | 0 | Repository hygiene passed | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | 11.7, G5 | `make lint-vnalpha` | 0 | Ruff checks passed; 582 files already formatted | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | 11.9, G5 | isolated writable `HOME`, log, knowledge, and workspace roots with `.venv/bin` first on `PATH`; `make test-vnalpha` | 0 | Complete vnalpha suite reached 100% with no failures | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | 11.10, G5 | same isolated environment; `make verify-r4` | 0 | 81 R4 tests passed | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | 11.11, G5 | same isolated environment; `packaging/scripts/openstock-verify --ci` | 0 | 16 OK, 1 expected systemd warning, 0 failures; status PASS | this ledger; command transcript |
| 2026-07-13T12:14:15Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | OpenSpec | `openspec validate symbol-knowledge-memory --strict` | 0 | Change is valid | this ledger; command transcript |
| 2026-07-13T12:18:00Z | 3af296419b04155e4aee16d45258f6d458fd8ba2 | 11.12 | Attach the exact-SHA evidence matrix to draft implementation PR #71 before checking G1-G5 | 0 | Evidence published at `https://github.com/duvu/openstock/pull/71`; G1-G5 then checked | PR #71 body |

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
