# Tasks: Close Phase 5 Alpha Discovery TUI Gaps

## 0. Baseline review

- [ ] Confirm archived Phase 5 spec exists at `openspec/specs/alpha-discovery-tui/spec.md`.
- [ ] Confirm `vnalpha/src/vnalpha/cli.py` contains placeholder commands for Phase 5 workflow commands.
- [ ] Confirm `candidate_score` table exists in warehouse schema.
- [ ] Confirm current watchlist generation writes `daily_watchlist` directly from in-memory scores.
- [ ] Confirm TUI detail currently recomputes score from `feature_snapshot`.
- [ ] Confirm current CLI tests mostly cover help text, not execution workflow.

## 1. Shared date resolver

- [ ] Add `vnalpha/src/vnalpha/core/dates.py`.
- [ ] Implement `resolve_date(value: str | None) -> str`.
- [ ] Support `today`.
- [ ] Support ISO `YYYY-MM-DD`.
- [ ] Reject invalid date values with clear errors.
- [ ] Add `vnalpha/tests/test_dates.py`.
- [ ] Use resolver in CLI build/score/watchlist/tui commands.
- [ ] Use resolver in TUI app and screens.

## 2. Wire CLI commands

- [ ] Update `vnalpha build features --date <date>` to call `vnalpha.features.build_features.build_features`.
- [ ] Ensure build features command runs migrations before use.
- [ ] Print built/skipped counts.
- [ ] Update `vnalpha score --date <date>` to call scoring persistence workflow.
- [ ] Print scored/persisted counts.
- [ ] Update `vnalpha watchlist --date <date>` to generate from persisted candidate scores.
- [ ] Print saved count or explicit no-candidate message.
- [ ] Update `vnalpha tui --date <date>` to launch `VnAlphaApp` with resolved date.
- [ ] Ensure no Phase 5 CLI command prints `not yet implemented`.
- [ ] Ensure top-level `Makefile` targets still work.

## 3. Candidate score persistence

- [ ] Add repository helper `save_candidate_score`.
- [ ] Add repository helper `get_candidate_score`.
- [ ] Add repository helper `get_candidate_scores`.
- [ ] Persist composite score.
- [ ] Persist candidate class.
- [ ] Persist setup type.
- [ ] Persist trend score.
- [ ] Persist relative strength score.
- [ ] Persist volume score.
- [ ] Persist base score.
- [ ] Persist breakout score.
- [ ] Persist risk quality score.
- [ ] Persist evidence JSON.
- [ ] Persist risk flags JSON.
- [ ] Persist lineage JSON.
- [ ] Ensure upsert behavior is deterministic for `(symbol, date)`.
- [ ] Add tests for candidate score save/read/upsert.

## 4. Evidence and lineage model

- [ ] Define deterministic evidence structure for scoring v1.
- [ ] Include rule outcomes or feature facts that explain the score.
- [ ] Include score component values.
- [ ] Include risk flags and reason fields.
- [ ] Include scoring version in lineage.
- [ ] Include feature date in lineage.
- [ ] Include source feature snapshot context in lineage.
- [ ] Include generated timestamp in lineage.
- [ ] Keep evidence and lineage JSON serializable and stable enough for tests.

## 5. Candidate taxonomy alignment

- [ ] Decide Phase 5 canonical candidate class taxonomy.
- [ ] Update spec delta to document canonical classes.
- [ ] Update scoring code if needed.
- [ ] Update tests if needed.
- [ ] Update TUI labels if needed.
- [ ] Preserve legacy enum values only as compatibility values if retained.
- [ ] Add tests proving emitted candidate classes are in the canonical set.

## 6. Watchlist generation from persisted candidate scores

- [ ] Refactor watchlist generation so `daily_watchlist` is derived from `candidate_score`.
- [ ] Do not recompute scores in watchlist generation.
- [ ] Preserve rank, score, candidate class, setup type, risk flags, and lineage in `daily_watchlist`.
- [ ] Return explicit no-candidate result when no candidate meets criteria.
- [ ] Add tests proving watchlist rows come from persisted candidate scores.
- [ ] Add tests for empty/no-candidate cases.

## 7. TUI reads persisted candidate records

- [ ] Update `VnAlphaApp` to carry resolved target date.
- [ ] Update `WatchlistScreen` to use app target date consistently.
- [ ] Update `DetailScreen` to read `candidate_score` for `(symbol, date)`.
- [ ] Display persisted score breakdown.
- [ ] Display persisted evidence.
- [ ] Display persisted risk flags.
- [ ] Display persisted lineage.
- [ ] Display feature snapshot values only as supporting context.
- [ ] Ensure selected watchlist symbol opens persisted detail.
- [ ] Add TUI smoke/data-loading tests.

## 8. Research-language boundary

- [ ] Create one test fixture for disallowed execution-style wording.
- [ ] Scan CLI output strings.
- [ ] Scan TUI visible strings where practical.
- [ ] Ensure candidate output uses research/watchlist language.
- [ ] Ensure empty-state and error-state messages use research language.
- [ ] Add regression tests for boundary wording.

## 9. End-to-end Phase 5 tests

- [ ] Add fixture warehouse with canonical OHLCV sufficient for features.
- [ ] Test `vnalpha build features --date <date>` through CLI runner.
- [ ] Test `vnalpha score --date <date>` persists candidate scores.
- [ ] Test `vnalpha watchlist --date <date>` persists daily watchlist rows.
- [ ] Test `vnalpha tui --help` still works.
- [ ] Test TUI data-loading helpers can read persisted candidate/watchlist data.
- [ ] Test no CLI command emits placeholder output.

## 10. Docs and runbook alignment

- [ ] Update `RUNBOOK.md` if command behavior changes.
- [ ] Update any Phase 5 notes that still imply tasks are complete before CLI wiring.
- [ ] Add troubleshooting note for empty watchlist.
- [ ] Add troubleshooting note for missing feature snapshots.
- [ ] Add note that Phase 6 outcome tracking remains future scope.

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

- [ ] Phase 5 CLI workflow is executable.
- [ ] `candidate_score` is the authoritative persisted score record.
- [ ] `daily_watchlist` is generated from `candidate_score`.
- [ ] TUI displays persisted candidate evidence and lineage.
- [ ] Candidate taxonomy is consistent across spec, code, tests, and UI.
- [ ] Date handling is deterministic.
- [ ] Research-language boundary is tested.
- [ ] End-to-end Phase 5 tests pass.
- [ ] Phase 5 can be archived as operationally closed.
