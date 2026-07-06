# Change: Complete Phase 5 Alpha Discovery MVP

## Change ID

`complete-phase-5-alpha-discovery-mvp`

## Status

Proposed

## Context

Phase 5 aims to provide the first useful deterministic research loop:

```text
vnstock-service
→ vnalpha sync
→ DuckDB research warehouse
→ canonical OHLCV
→ feature snapshots
→ candidate scores
→ daily watchlist
→ CLI/TUI review surface
```

A codebase review shows that Phase 5 is no longer only a skeleton. `vnalpha` already has:

- CLI command routing for `init`, `sync symbols`, `sync ohlcv`, `build canonical`, `build features`, `score`, `watchlist`, and `tui`.
- DuckDB warehouse migrations and tables.
- `vnstock-service` HTTP client.
- symbol and OHLCV ingestion modules.
- canonical OHLCV builder.
- feature builder.
- deterministic scoring and watchlist generation.
- TUI screens for watchlist, detail, rejected symbols, and data quality.
- basic scoring/watchlist tests.

However, the codebase still has Phase 5 completion gaps that can prevent reliable end-to-end operation.

## Problems Found

### 1. CLI and Makefile command contract mismatch

`Makefile` calls:

```bash
vnalpha sync ohlcv --universe VN30 --start 2024-01-01
```

But the current CLI exposes `--symbols`, not `--universe`, for `vnalpha sync ohlcv`.

This means `make sync` can fail before the pipeline reaches canonicalization.

### 2. Benchmark ingestion is not explicit

`build_features()` computes relative strength against `VNINDEX`, but the normal sync flow only syncs equity OHLCV symbols. If `VNINDEX` is not already present in `canonical_ohlcv`, relative strength features degrade to `NaN`.

Phase 5 needs an explicit benchmark sync/build contract.

### 3. Watchlist artifact is thinner than the Phase 5 Definition of Done

`daily_watchlist` currently stores rank, symbol, score, candidate class, setup type, risk flags, and lineage. It does not directly store evidence or data-quality status.

The Phase 5 output requires:

```text
symbol
score
candidate_class
setup_type
evidence
risk_flags
provider lineage
data quality status
```

The detail screen can read evidence from `candidate_score`, but the watchlist artifact itself and CLI table do not yet expose all required fields.

### 4. TUI navigation is incomplete

`VnAlphaApp` binds home/rejected/quality actions, but currently pushes named screens such as `home`, `rejected`, and `quality`. These screens must be registered or pushed as screen instances.

### 5. Ontology exists but legacy aliases remain too permissive

Canonical enums exist for `candidate_class` and `setup_type`, but legacy aliases remain inside the same enums. Tests currently allow all enum values, including legacy values.

Phase 5 should enforce canonical values in persisted `candidate_score` and `daily_watchlist` rows.

### 6. E2E test coverage is incomplete

There are scoring and watchlist tests, but Phase 5 needs a fixture-backed end-to-end test that validates:

```text
migrations
→ fixture symbol/OHLCV load
→ canonical build
→ feature build
→ scoring
→ watchlist query
→ CLI command contract
→ TUI smoke construction
```

Provider-backed smoke tests can remain optional, but CI must not depend on external data providers.

## Goals

- Make Phase 5 executable through both Makefile and direct CLI commands.
- Align CLI contract with roadmap/runbook commands.
- Add explicit benchmark data handling for relative strength features.
- Ensure watchlist and detail surfaces expose evidence, risk flags, lineage, and data quality status.
- Fix TUI navigation for all required Phase 5 screens.
- Enforce canonical candidate/setup ontology in persisted data.
- Add deterministic fixture-backed E2E tests.
- Keep Phase 5 research-only and non-execution-oriented.

## Non-Goals

- No MCP integration.
- No natural-language prompt UX.
- No Python research sandbox.
- No backtest lab.
- No outcome tracking beyond fields required to support future Phase 6.
- No ML ranking.
- No brokerage order/account/portfolio integration.

## Proposed Solution

Implement a Phase 5 completion patch in `vnalpha` with the following areas:

1. Command contract hardening.
2. Benchmark ingestion and canonicalization support.
3. Watchlist artifact completion.
4. TUI screen registration/navigation fixes.
5. Canonical ontology enforcement.
6. Fixture-backed E2E tests.
7. Runbook/Makefile alignment.

## Acceptance Criteria

Phase 5 is complete when:

- `make sync` succeeds or has a documented fixture-mode equivalent in CI.
- `vnalpha sync ohlcv --universe VN30` works, or Makefile is changed to the supported CLI contract.
- benchmark OHLCV for `VNINDEX` can be synced and built into `canonical_ohlcv`.
- `vnalpha build features --date <date>` produces feature rows with relative strength fields when benchmark data exists.
- `vnalpha score --date <date>` persists `candidate_score` rows and regenerates `daily_watchlist`.
- `daily_watchlist` or its query view exposes evidence, risk flags, lineage, and data quality status.
- `vnalpha watchlist --date <date>` renders the required review fields or has a detail command path for them.
- `vnalpha tui --date <date>` launches and all bound screens work.
- fixture-backed E2E tests pass without network access.
- persisted `candidate_class` values are limited to canonical classes.
- persisted `setup_type` values are limited to canonical setup types.
- no command or TUI screen exposes buy/sell/order/portfolio language.

## Validation Commands

```bash
make install-vnalpha
make lint-vnalpha
make test-vnalpha
make sync
make features
make score
make tui
```

CI-safe validation:

```bash
cd vnalpha
pytest -q tests/test_phase5_e2e.py
pytest -q tests/test_cli_contract.py
pytest -q tests/test_tui_smoke.py
```

## Rollout Plan

1. Patch CLI/Makefile command mismatch.
2. Add benchmark sync/build path.
3. Extend watchlist artifact/query output.
4. Fix TUI screen navigation.
5. Add canonical ontology guards.
6. Add fixture-backed E2E tests.
7. Update runbook and OpenSpec task status.
8. Close Phase 5 only after tests and smoke commands pass.
