# Tasks: Auto data provisioning for symbol analysis

## 0. Governance

- [x] 0.1 Treat this as runtime implementation work, not a docs-only change.
- [x] 0.2 Keep manual sync/build/score commands working unchanged.
- [x] 0.3 Keep one-symbol analysis provisioning minimal; do not auto-refresh the full universe by default.
- [x] 0.4 Preserve the read-only research boundary.
- [x] 0.5 Preserve redaction-by-default logging behavior.
- [x] 0.6 Do not mark tasks complete without code, tests, and validation evidence.

## 1. Data availability package

- [x] 1.1 Add `vnalpha/src/vnalpha/data_availability/__init__.py`.
- [x] 1.2 Add `models.py` with `EnsureDataResult`, status enum, and action enum/string constants.
- [x] 1.3 Add `policy.py` with `DataAvailabilityPolicy`.
- [x] 1.4 Add `checks.py` with artifact status checks.
- [x] 1.5 Add `ensure.py` with `ensure_symbol_analysis_ready()`.
- [x] 1.6 Add `observability.py` or equivalent helper for `DATA_ENSURE_*` events.
- [x] 1.7 Add unit tests for model serialization or dict conversion.

## 2. Artifact checks

- [x] 2.1 Check whether symbol exists in `symbol_master`.
- [x] 2.2 Check whether `candidate_score(symbol, target_date)` exists.
- [x] 2.3 Check whether `feature_snapshot(symbol, target_date)` exists.
- [x] 2.4 Check whether `canonical_ohlcv` has enough symbol history up to target date.
- [x] 2.5 Check whether benchmark canonical data exists and has enough history.
- [x] 2.6 Return row counts for symbol and benchmark.
- [x] 2.7 Return latest bar date and as-of bar date.
- [x] 2.8 Return stale/insufficient flags.
- [x] 2.9 Return lineage fields where available.
- [x] 2.10 Add tests for all checks using in-memory DuckDB.

## 3. Freshness and lookback policy

- [x] 3.1 Define default benchmark symbol `VNINDEX`.
- [x] 3.2 Define default lookback window, initially 420 calendar days.
- [x] 3.3 Define minimum required bars, initially 120.
- [x] 3.4 Define stale policy for latest bar date vs target date.
- [x] 3.5 Handle non-trading target dates by using latest bar on or before target date.
- [x] 3.6 Expose `auto_sync` policy flag.
- [ ] 3.7 Expose source/provider override.
- [ ] 3.8 Add tests for weekend/non-trading target date behavior.

## 4. Ensure-data algorithm

- [x] 4.1 Normalize symbol and target date.
- [x] 4.2 Compute lookback start date.
- [x] 4.3 Emit `DATA_ENSURE_STARTED`.
- [x] 4.4 Return cache hit if candidate score and supporting freshness are sufficient.
- [x] 4.5 Sync symbol master when needed and auto_sync is enabled.
- [x] 4.6 Sync requested symbol OHLCV when canonical data is missing/stale/insufficient.
- [x] 4.7 Sync benchmark OHLCV when benchmark data is missing/stale/insufficient.
- [x] 4.8 Build canonical OHLCV for requested symbol after symbol sync.
- [x] 4.9 Build canonical OHLCV for benchmark after benchmark sync.
- [x] 4.10 Build feature snapshot for requested symbol when missing.
- [x] 4.11 Generate candidate score for requested symbol when missing.
- [x] 4.12 Re-check final artifact status after actions.
- [x] 4.13 Return `READY` if candidate_score exists after provisioning.
- [x] 4.14 Return `PARTIAL` if some artifacts exist but score is still unavailable.
- [x] 4.15 Return `FAILED` for unrecoverable failures.
- [x] 4.16 Add tests for cache hit, score-only, feature-only, canonical-missing, benchmark-missing, and failed paths.

## 5. Dependency injection and testability

- [x] 5.1 Allow injecting sync/build/score callables for tests.
- [ ] 5.2 Allow injecting `VnstockClient` or client factory.
- [x] 5.3 Ensure tests do not call real vnstock-service.
- [ ] 5.4 Add fake provider response fixtures.
- [x] 5.5 Add failure fixtures for service unavailable and empty provider data.

## 6. `/explain SYMBOL` integration

- [x] 6.1 Call `ensure_symbol_analysis_ready()` before `candidate.explain`.
- [x] 6.2 If ensure returns `FAILED`, return `CommandResult(status="FAILED")` with actionable error summary.
- [x] 6.3 If ensure returns `PARTIAL`, continue only when candidate_score exists; otherwise return partial result with warnings.
- [x] 6.4 If ensure returns `READY`, call existing `candidate.explain` tool.
- [x] 6.5 Add a `Data Readiness` panel to `/explain` output.
- [x] 6.6 Include actions taken, cache hits, warnings, freshness, and lineage in the panel.
- [ ] 6.7 Add tests: `/explain FPT` missing score triggers ensure and returns analysis.
- [ ] 6.8 Add tests: `/explain FPT` cache hit does not sync/build/score.
- [ ] 6.9 Add tests: ensure failure returns clear command failure.

## 7. `/compare` integration

- [x] 7.1 Ensure each requested symbol before `candidate.compare`.
- [x] 7.2 Avoid duplicate ensure calls for repeated symbols.
- [x] 7.3 Compare ready symbols.
- [x] 7.4 If some symbols fail, include warnings per symbol.
- [x] 7.5 If all symbols fail, return command failure.
- [ ] 7.6 Add a `Data Readiness` panel to compare results.
- [ ] 7.7 Add tests for mixed ready/failed symbols.

## 8. Assistant integration

- [x] 8.1 Add deterministic pre-execution ensure-data hook before `candidate.explain`.
- [x] 8.2 Add deterministic pre-execution ensure-data hook before `candidate.compare`.
- [x] 8.3 Do not require the LLM to plan data-sync steps.
- [x] 8.4 Include ensure-data result in tool output or synthesis context.
- [x] 8.5 Preserve existing read-tool allowlist behavior.
- [ ] 8.6 Add tests for natural-language `explain_symbol` path triggering ensure.
- [ ] 8.7 Add tests for natural-language `compare_symbols` path triggering ensure.

## 9. Optional `/scan --auto-refresh`

- [x] 9.1 Keep default `/scan` artifact-read behavior unchanged.
- [ ] 9.2 Add optional `--auto-refresh` only if feasible.
- [ ] 9.3 If added, document that full-universe refresh can be slow.
- [x] 9.4 If not added in first implementation, document as future work.

## 10. Observability

- [x] 10.1 Emit `DATA_ENSURE_STARTED`.
- [x] 10.2 Emit `DATA_ENSURE_CACHE_HIT`.
- [x] 10.3 Emit sync started/succeeded/failed events for symbol OHLCV.
- [x] 10.4 Emit sync started/succeeded/failed events for benchmark OHLCV.
- [x] 10.5 Emit canonical build started/succeeded/failed events.
- [x] 10.6 Emit feature build started/succeeded/failed events.
- [x] 10.7 Emit score started/succeeded/failed events.
- [x] 10.8 Emit `DATA_ENSURE_READY`, `DATA_ENSURE_PARTIAL`, or `DATA_ENSURE_FAILED`.
- [x] 10.9 Include symbol, target date, benchmark, action, row count, latest bar date, and error details.
- [ ] 10.10 Add tests proving observability events are emitted.

## 11. Locking and idempotency

- [ ] 11.1 Add local lock per symbol/date ensure flow.
- [ ] 11.2 Ensure stale locks are detected and handled.
- [ ] 11.3 Ensure lock is released in `finally`.
- [ ] 11.4 Do not fail if another request already completed the provisioning while waiting.
- [ ] 11.5 Add tests for duplicate ensure calls.

## 12. Failure handling

- [x] 12.1 Handle vnstock-service unavailable.
- [x] 12.2 Handle provider empty data.
- [x] 12.3 Handle unknown symbol.
- [x] 12.4 Handle insufficient history after sync.
- [x] 12.5 Handle missing benchmark.
- [x] 12.6 Handle canonical build failure.
- [x] 12.7 Handle feature build failure.
- [x] 12.8 Handle scoring failure.
- [x] 12.9 Ensure user-facing errors are actionable.
- [x] 12.10 Add tests for each failure mode.

## 13. Documentation

- [x] 13.1 Add `vnalpha/docs/auto-data-provisioning.md`.
- [x] 13.2 Document when auto provisioning runs.
- [x] 13.3 Document freshness policy.
- [x] 13.4 Document how to disable auto sync.
- [ ] 13.5 Document manual fallback commands.
- [x] 13.6 Document troubleshooting for vnstock-service issues.
- [x] 13.7 Document performance considerations.

## 14. Validation

- [x] 14.1 Run `make test-vnalpha`. — 1123 passed, 1 skipped (pre-existing TUI renderer test)
- [x] 14.2 Run `make lint-vnalpha`. — All checks passed
- [x] 14.3 Run `make verify-r4`. — 80 passed
- [x] 14.4 Run `openstock-verify --ci`. — 16 OK, 1 WARN, 0 FAIL
- [x] 14.5 Add validation evidence showing mocked `/explain FPT` provisions missing data. — test_data_availability_ensure.py::TestAutoSyncPath
- [x] 14.6 Add validation evidence showing cache hit avoids unnecessary sync/build/score. — test_data_availability_ensure.py::TestCacheHit
- [x] 14.7 Add validation evidence showing service failure returns clear error. — test_data_availability_ensure.py::TestNoCrashOnSyncFailure
