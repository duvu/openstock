# Change: Close Phase 5 Alpha Discovery TUI MVP

## Change ID

`close-phase-5-alpha-discovery-tui-mvp`

## Status

Proposed

## Context

Phase 5 already has roadmap/spec coverage for the Alpha Discovery TUI MVP, but the implementation should not be treated as closed until the user-facing workflow is executable end-to-end.

Current review context indicates these blockers:

- `vnalpha build features` is still stubbed or not wired to a real feature-building pipeline.
- `vnalpha score` is still stubbed or not wired to candidate scoring and watchlist generation.
- `vnalpha watchlist` is still stubbed or does not query `daily_watchlist` from DuckDB.
- `vnalpha tui` is still stubbed or does not launch the Textual app.
- `candidate_class` labels are inconsistent between roadmap/spec and implementation.
- Existing task checkboxes may overstate completion because several items are checked without executable verification.
- Repo boundary is unresolved: `openstock` is intended to be orchestration/source-of-truth, while `vnalpha` should contain implementation unless the project intentionally vendors it.

## Problem

Phase 5 cannot be closed by documentation alone. It must demonstrate this executable workflow:

```text
vnstock-service
→ vnalpha sync
→ DuckDB warehouse
→ canonical OHLCV
→ feature snapshot
→ candidate score
→ daily watchlist
→ CLI/TUI review surface
```

## Goals

- Convert the existing Phase 5 skeleton into an executable deterministic MVP.
- Wire CLI commands to real implementation modules instead of stubs.
- Generate canonical OHLCV, feature snapshots, candidate scores, and daily watchlist rows.
- Render the watchlist in CLI and TUI.
- Add fixture-backed end-to-end tests using an isolated DuckDB database.
- Correct task status so Phase 5 is only marked closed after verification.
- Resolve or explicitly document the `vnalpha` repo boundary.

## Non-Goals

- No trading execution.
- No brokerage account integration.
- No portfolio execution.
- No MCP client implementation in this closure change.
- No LLM Gateway planner/explainer implementation in this closure change.
- No ML ranking model.
- No full backtest lab.
- No Phase 6 outcome feedback loop beyond Phase 5-compatible watchlist rows.

MCP and LLM Gateway work should be specified separately as Phase 5.8 / Phase 5.9 or later.

## Proposed Solution

Implement and verify the Phase 5 deterministic research pipeline:

1. Wire `vnalpha` CLI commands to implementation modules.
2. Build canonical OHLCV from synced raw data.
3. Build feature snapshots from canonical OHLCV.
4. Score symbols using deterministic scoring functions.
5. Generate daily watchlist rows.
6. Render watchlist output in CLI and TUI.
7. Add fixture-based end-to-end tests.
8. Update OpenSpec tasks so checked items represent verified work only.

## Candidate Ontology Decision

Use separate concepts:

```text
candidate_class = final prioritization class
setup_type      = observed technical setup label
```

Canonical `candidate_class` values:

- `STRONG_CANDIDATE`
- `WATCH_CANDIDATE`
- `WEAK_CANDIDATE`
- `IGNORE`

Canonical `setup_type` values:

- `ACCUMULATION_BASE`
- `BREAKOUT_ATTEMPT`
- `MOMENTUM_CONTINUATION`
- `PULLBACK_TO_TREND`
- `MEAN_REVERSION`
- `UNCLASSIFIED`

Existing labels such as `STAGE1`, `STAGE2`, `BREAKOUT`, `MOMENTUM`, and `MEAN_REVERT` must not be stored as `candidate_class`. They should be mapped to `setup_type` or removed.

## Acceptance Criteria

Phase 5 is closable only when all of the following are true:

- `vnalpha init` creates or migrates the DuckDB warehouse schema.
- `vnalpha sync symbols` stores symbol metadata.
- `vnalpha sync ohlcv --universe VN30` stores OHLCV raw data, or CI uses fixture data.
- `vnalpha build canonical` creates `canonical_ohlcv`.
- `vnalpha build features` creates `feature_snapshot`.
- `vnalpha score` creates `candidate_score` and `daily_watchlist`.
- `vnalpha watchlist` prints a Rich table from `daily_watchlist`.
- `vnalpha tui` launches `VnAlphaApp().run()`.
- Watchlist detail view shows score breakdown, evidence, risk flags, lineage, and data quality.
- Fixture-backed end-to-end tests pass against isolated DuckDB.
- Public CLI/TUI/docs remain research/watchlist/candidate oriented and do not expose execution-oriented commands.
- OpenSpec task checklist is updated so only tested/verified work is checked.

## Validation Commands

```bash
make install-vnalpha
make test-vnalpha
make lint-vnalpha
make up-vnstock
make sync
make features
make score
make tui
```

Direct CLI validation:

```bash
vnalpha init
vnalpha sync symbols --universe VN30
vnalpha sync ohlcv --universe VN30
vnalpha build canonical
vnalpha build features
vnalpha score
vnalpha watchlist
vnalpha tui
```

For CI, external data dependencies should be replaced by fixture OHLCV data.

## Rollout Plan

1. Patch `vnalpha` implementation and tests.
2. Run deterministic fixture-backed tests.
3. Run local service-backed smoke test with `vnstock-service`.
4. Update OpenSpec task status based on actual verification.
5. Confirm repo boundary and commit implementation to the correct repository.
6. Mark Phase 5 closed only after acceptance criteria pass.

## Risks

- External provider data may be unstable or rate-limited.
- DuckDB schema migrations may drift from code expectations.
- TUI screens may launch but not display real data.
- Task checkboxes may be updated without executable verification.
- Repo boundary confusion may leave implementation in the wrong repository.

## Risk Controls

- Use fixture-based E2E tests for deterministic CI.
- Keep provider-backed tests as smoke/integration tests.
- Treat task completion as invalid unless linked to tests, commands, or executable code paths.
- Keep `openstock` as orchestration unless vendoring is deliberately recorded.
