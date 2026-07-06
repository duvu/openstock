# Tasks: Close Phase 5 Alpha Discovery TUI Gaps

## 0. Baseline review

- [x] Confirm archived Phase 5 spec exists at `openspec/specs/alpha-discovery-tui/spec.md`.
- [x] Confirm `vnalpha/src/vnalpha/cli.py` contains placeholder commands for Phase 5 workflow commands.
- [x] Confirm `candidate_score` table exists in warehouse schema.
- [x] Confirm current watchlist generation writes `daily_watchlist` directly from in-memory scores.
- [x] Confirm TUI detail currently recomputes score from `feature_snapshot`.
- [x] Confirm current CLI tests mostly cover help text, not execution workflow.

## 1. Shared date resolver

- [x] Add `vnalpha/src/vnalpha/core/dates.py`.
- [x] Implement `resolve_date(value: str | None) -> str`.
- [x] Support `today`.
- [x] Support ISO `YYYY-MM-DD`.
- [x] Reject invalid date values with clear errors.
- [x] Add `vnalpha/tests/test_dates.py`.
- [x] Use resolver in CLI build/score/watchlist/tui commands.
- [x] Use resolver in TUI app and screens.

## 2. Wire CLI commands

- [x] Update `vnalpha build features --date <date>` to call `vnalpha.features.build_features.build_features`.
- [x] Ensure build features command runs migrations before use.
- [x] Print built/skipped counts.
- [x] Update `vnalpha score --date <date>` to call scoring persistence workflow.
- [x] Print scored/persisted counts.
- [x] Update `vnalpha watchlist --date <date>` to generate from persisted candidate scores.
- [x] Print saved count or explicit no-candidate message.
- [x] Update `vnalpha tui --date <date>` to launch `VnAlphaApp` with resolved date.
- [x] Ensure no Phase 5 CLI command prints `not yet implemented`.
- [x] Ensure top-level `Makefile` targets still work.

## 3. Candidate score persistence

- [x] Add repository helper `save_candidate_score`.
- [x] Add repository helper `get_candidate_score`.
- [x] Add repository helper `get_candidate_scores`.
- [x] Persist composite score.
- [x] Persist candidate class.
- [x] Persist setup type.
- [x] Persist trend score.
- [x] Persist relative strength score.
- [x] Persist volume score.
- [x] Persist base score.
- [x] Persist breakout score.
- [x] Persist risk quality score.
- [x] Persist evidence JSON.
- [x] Persist risk flags JSON.
- [x] Persist lineage JSON.
- [x] Ensure upsert behavior is deterministic for `(symbol, date)`.
- [x] Add tests for candidate score save/read/upsert.

## 4. Evidence and lineage model

- [x] Define deterministic evidence structure for scoring v1.
- [x] Include rule outcomes or feature facts that explain the score.
- [x] Include score component values.
- [x] Include risk flags and reason fields.
- [x] Include scoring version in lineage.
- [x] Include feature date in lineage.
- [x] Include source feature snapshot context in lineage.
- [x] Include generated timestamp in lineage.
- [x] Keep evidence and lineage JSON serializable and stable enough for tests.

## 5. Candidate taxonomy alignment

- [x] Decide Phase 5 canonical candidate class taxonomy.
- [x] Update spec delta to document canonical classes.
- [x] Update scoring code if needed.
- [x] Update tests if needed.
- [x] Update TUI labels if needed.
- [x] Preserve legacy enum values only as compatibility values if retained.
- [x] Add tests proving emitted candidate classes are in the canonical set.

## 6. Watchlist generation from persisted candidate scores

- [x] Refactor watchlist generation so `daily_watchlist` is derived from `candidate_score`.
- [x] Do not recompute scores in watchlist generation.
- [x] Preserve rank, score, candidate class, setup type, risk flags, and lineage in `daily_watchlist`.
- [x] Return explicit no-candidate result when no candidate meets criteria.
- [x] Add tests proving watchlist rows come from persisted candidate scores.
- [x] Add tests for empty/no-candidate cases.

## 7. TUI reads persisted candidate records

- [x] Update `VnAlphaApp` to carry resolved target date.
- [x] Update `WatchlistScreen` to use app target date consistently.
- [x] Update `DetailScreen` to read `candidate_score` for `(symbol, date)`.
- [x] Display persisted score breakdown.
- [x] Display persisted evidence.
- [x] Display persisted risk flags.
- [x] Display persisted lineage.
- [x] Display feature snapshot values only as supporting context.
- [x] Ensure selected watchlist symbol opens persisted detail.
- [x] Add TUI smoke/data-loading tests.

## 8. Research-language boundary

- [x] Create one test fixture for disallowed execution-style wording.
- [x] Scan CLI output strings.
- [x] Scan TUI visible strings where practical.
- [x] Ensure candidate output uses research/watchlist language.
- [x] Ensure empty-state and error-state messages use research language.
- [x] Add regression tests for boundary wording.

## 9. End-to-end Phase 5 tests

- [x] Add fixture warehouse with canonical OHLCV sufficient for features.
- [x] Test `vnalpha build features --date <date>` through CLI runner.
- [x] Test `vnalpha score --date <date>` persists candidate scores.
- [x] Test `vnalpha watchlist --date <date>` persists daily watchlist rows.
- [x] Test `vnalpha tui --help` still works.
- [x] Test TUI data-loading helpers can read persisted candidate/watchlist data.
- [x] Test no CLI command emits placeholder output.

## 10. Docs and runbook alignment

- [x] Update `RUNBOOK.md` if command behavior changes.
- [x] Update any Phase 5 notes that still imply tasks are complete before CLI wiring.
- [x] Add troubleshooting note for empty watchlist.
- [x] Add troubleshooting note for missing feature snapshots.
- [x] Add note that Phase 6 outcome tracking remains future scope.

## 11. Validation

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

Optional local workflow:

```bash
make up-vnstock
make sync
make features
make score
make tui
```

## Completion checklist

- [x] Phase 5 CLI workflow is executable.
- [x] `candidate_score` is the authoritative persisted score record.
- [x] `daily_watchlist` is generated from `candidate_score`.
- [x] TUI displays persisted candidate evidence and lineage.
- [x] Candidate taxonomy is consistent across spec, code, tests, and UI.
- [x] Date handling is deterministic.
- [x] Research-language boundary is tested.
- [x] End-to-end Phase 5 tests pass.
- [x] Phase 5 can be archived as operationally closed.
