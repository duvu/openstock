# Change Proposal: Close Phase 5 Alpha Discovery TUI Gaps

## Change ID

`close-phase-5-alpha-discovery-tui-gaps`

## Summary

Close the remaining implementation gaps in Phase 5 Alpha Discovery TUI MVP so the archived Phase 5 spec is operationally true, not only structurally present.

Phase 5 already has the main building blocks:

- `openstock` orchestration targets;
- `vnalpha` package skeleton;
- `vnstock-service` HTTP client;
- DuckDB warehouse schema;
- ingestion modules;
- deterministic feature builders;
- scoring modules;
- watchlist generator;
- TUI screens.

The remaining gap is integration closure: CLI commands must call the implementation, candidate scores must be persisted as the canonical research record, TUI must read persisted evidence and lineage, and tests must prove the complete local daily workflow.

## Background

The archived Phase 5 spec says the local workflow should run:

```text
vnstock-service
→ vnalpha sync
→ DuckDB research warehouse
→ feature store v1
→ alpha scoring v1
→ daily watchlist
→ TUI workspace
```

Current code contains much of this implementation, but the top-level user-facing commands still do not execute the full pipeline. In particular, the CLI placeholders make `make features`, `make score`, `make tui`, and equivalent `vnalpha` commands incomplete from a product workflow perspective.

## Problems to fix

1. `vnalpha build features`, `vnalpha score`, `vnalpha watchlist`, and `vnalpha tui` are not wired to their implementation modules.
2. `candidate_score` exists in the warehouse schema but is not yet the authoritative persisted research record for scoring output.
3. `daily_watchlist` is generated directly from in-memory scores instead of from persisted candidate records.
4. TUI symbol detail recomputes score from `feature_snapshot` instead of reading persisted score, evidence, risk flags, and lineage.
5. Candidate class naming is inconsistent between the archived spec and scoring engine v1 enums.
6. Date handling is spread across CLI, feature build, scoring, watchlist, and TUI; `today` should be resolved consistently.
7. Tests mostly prove module behavior and help text; they do not yet prove the complete Phase 5 CLI workflow.
8. Research-language and execution-boundary tests should cover CLI/TUI outputs, not only isolated strings.

## Goals

### G1. Wire end-to-end CLI commands

`vnalpha build features`, `vnalpha score`, `vnalpha watchlist`, and `vnalpha tui` must call real implementation paths and return useful terminal output.

### G2. Make `candidate_score` authoritative

Scoring must persist one candidate score record per `(date, symbol)` with score breakdown, evidence, risk flags, setup type, candidate class, and lineage.

### G3. Generate watchlist from persisted candidate records

`daily_watchlist` must be derived from `candidate_score`, not from transient in-memory scoring output.

### G4. Align candidate taxonomy

Choose and document the Phase 5 canonical candidate class taxonomy, then make code, tests, TUI, and spec consistent.

### G5. Make TUI detail explain persisted candidates

TUI detail must show the persisted candidate record, including score breakdown, evidence, risk flags, and lineage. It may show feature values as supporting context, but it must not silently recompute a different score.

### G6. Add deterministic date handling

Create one date resolver for `today` and ISO date strings, then reuse it across CLI, scoring, watchlist, and TUI.

### G7. Add end-to-end validation tests

Tests must prove the local daily research workflow from warehouse fixture to features, scoring, watchlist, and TUI-readable records.

## Non-goals

This change does not implement:

- ML ranking;
- backtest lab;
- outcome tracking for Phase 6;
- realtime streaming;
- broker integration;
- portfolio features;
- web dashboard;
- Streamlit;
- production scheduler;
- new data providers.

## Success criteria

This change is complete when:

1. no Phase 5 user-facing CLI command prints a placeholder message;
2. `make features`, `make score`, and `make tui` execute real `vnalpha` workflows;
3. `candidate_score` rows are persisted for scored symbols;
4. `daily_watchlist` rows are generated from `candidate_score` rows;
5. candidate detail in TUI comes from persisted candidate data;
6. empty/no-candidate cases are explicit and non-error;
7. candidate taxonomy is consistent across spec, code, tests, and TUI;
8. date resolution is consistent for `today` and explicit dates;
9. tests cover CLI execution, scoring persistence, watchlist persistence, TUI data loading, and research-language boundary;
10. Phase 5 can be archived as operationally closed after validation passes.

## Validation commands

Run from repo root:

```bash
make install-vnalpha
make test-vnalpha
```

Run inside `vnalpha`:

```bash
ruff check .
ruff format --check .
pytest -q
vnalpha --help
vnalpha build features --date today
vnalpha score --date today
vnalpha watchlist --date today
vnalpha tui --help
```

Optional local service workflow:

```bash
make up-vnstock
make sync
make features
make score
make tui
```
