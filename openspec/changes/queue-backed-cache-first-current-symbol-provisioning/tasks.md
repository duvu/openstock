# Tasks: Queue-backed cache-first research runtime

A task is complete only when its named code, focused tests and exact-SHA evidence exist.

## 1. Warehouse ownership — #343

- [x] 1.1 Remove production warehouse copy/fallback behavior.
- [x] 1.2 Add short-lived read-only connections for readiness and analysis.
- [x] 1.3 Add one `WarehouseWriteCoordinator` and global lock.
- [x] 1.4 Route migrations, provisioning, finalization, outcomes, memory/context and metadata writes through the coordinator.
- [x] 1.5 Add writer-exclusion, rollback and typed-open-failure tests.

## 2. Readiness and goal contracts — #320, #338

- [x] 2.1 Add artifact states and capability-scoped readiness.
- [x] 2.2 Add source/provider/auth/persistence-aware repairability.
- [x] 2.3 Report exact missing ranges and bounded actions without writing or calling providers.
- [x] 2.4 Add versioned models for `ENSURE_CURRENT_SYMBOL`, `SYNC_DATASET_RANGE` and `FINALIZE_MARKET_SESSION`. Evidence: `9a6f516843eda890bd5d13e9bbfc4a7612e2eecc`, hardened by `d09efd351c9297c91bda18355b13979c02635036`; supported source-policy and contract versions fail closed before queue persistence or handler execution.
- [x] 2.5 Add deterministic identities, enrichment normalization and collision tests. Evidence: `d09efd351c9297c91bda18355b13979c02635036`; authoritative `vnalpha/tests/test_provisioning_queue_goals.py::test_provisioning_goal_contract`; `make test-loop TEST=tests/test_provisioning_queue_goals.py::test_provisioning_goal_contract` passed; `uv run python ../scripts/run_test_suite.py --plan --domain application` validates the authoritative inventory.

## 3. Queue repository — #323

- [x] 3.1 Add SQLite schema, migrations and explicit WAL/busy-timeout settings. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820`, separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`, and boundary-corrected by `7729b21e9d4d52d64390d4ffea29b8f5e24c2bb1`.
- [x] 3.2 Implement submit-or-join with priority escalation. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`.
- [x] 3.3 Implement atomic claim, lease, heartbeat and bounded retry. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`.
- [x] 3.4 Implement status, terminal result, cancellation and size limits. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`.
- [x] 3.5 Prove concurrent submit/claim/status behavior without DuckDB access. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`; authoritative `vnalpha/tests/test_provisioning_queue_repository.py::test_durable_provisioning_queue_contract`; `make test-loop TEST=tests/test_provisioning_queue_repository.py::test_durable_provisioning_queue_contract` passed; `uv run python ../scripts/run-test-suite.py --plan --domain application` validates the authoritative inventory.

## 4. Sequential worker — #324

- [x] 4.1 Add one worker and explicit handler registry. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`, hardened by `079c32dfa3d59fd9bb345d5b730a0112035c2d45`; authoritative `vnalpha/tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract`.
- [x] 4.2 Open writable DuckDB only through #343 after lock acquisition. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`; the worker injects `WarehouseWriteCoordinator` and the contract verifies an unregistered goal creates no warehouse file.
- [x] 4.3 Re-read and re-plan after claim. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`, hardened by `079c32dfa3d59fd9bb345d5b730a0112035c2d45`; the current-symbol handler delegates core price/ranking work to the existing current-symbol operation and the restart contract proves persisted effects are reused. Enrichment and source-policy execution remain with their owning changes.
- [ ] 4.4 Add bounded stage timeouts, lease extension and cooperative stop behavior. Partial evidence: `079c32dfa3d59fd9bb345d5b730a0112035c2d45` maintains the active lease and acknowledges cancellation at safe boundaries. A hard timeout cannot safely interrupt the existing synchronous DuckDB operation, and signal shutdown lacks an authoritative probe; both remain incomplete.
- [x] 4.5 Prove retry after process interruption creates no duplicate persisted artifacts. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`, hardened by `079c32dfa3d59fd9bb345d5b730a0112035c2d45`; `make test-loop TEST=tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract` passed with committed-effect/expired-lease restart reuse and an active-stage lease-overrun probe.

## 5. Provisioning behavior — #318, #319, #321

- [ ] 5.1 Ready same-date requests return without a queue job or write work.
- [ ] 5.2 Compute exact missing OHLCV tails and bounded repair ranges.
- [ ] 5.3 Avoid provider calls when raw evidence is ready and canonical evidence is stale.
- [ ] 5.4 Add date-bounded canonical promotion.
- [ ] 5.5 Stop dependent actions after the first failed prerequisite and record `BLOCKED`.
- [ ] 5.6 Add row-count, function-call and same-date idempotency tests.

## 6. Interactive application — #325, #322

- [ ] 6.1 Add queue client operations without holding DuckDB while waiting.
- [ ] 6.2 Implement shared `WAIT_UNTIL_TERMINAL`, `WAIT_UP_TO` and `DETACH` defaults.
- [ ] 6.3 Add priority escalation and explicit shared-job cancellation warnings.
- [ ] 6.4 Add `CurrentSymbolResearchApplication` as the single CLI/TUI/chat boundary.
- [ ] 6.5 Replace the assistant's unconditional provision-then-analyze plan with one application operation.
- [ ] 6.6 Enforce `READY|DEGRADED|ACCEPTED|PENDING|UNAVAILABLE|FAILED` and claim limitations.
- [ ] 6.7 Add cross-surface parity and no-analysis tests for non-analysis states.

## 7. Maintenance producer — #326

- [ ] 7.1 Add maintenance states, frozen universe/session/source-policy fields and expected goal identities.
- [ ] 7.2 Add idempotent `maintenance_run_job` mapping.
- [ ] 7.3 Implement phased resume across DuckDB ledger and SQLite queue updates.
- [ ] 7.4 Enqueue VNINDEX as dataset-range work and equities as `PRICE_ANALYSIS` goals.
- [ ] 7.5 Ensure acquisition does not build batch features, scores or watchlists.
- [ ] 7.6 Return enqueue/detach evidence, never final daily success.

## 8. Session finalization — #337

- [ ] 8.1 Add idempotent `maybe_submit_session_finalization()` trigger.
- [ ] 8.2 Guard against unmapped or active expected jobs.
- [ ] 8.3 Add the finalization handler and state transitions.
- [ ] 8.4 Build features and score/watchlist once for the frozen eligible universe.
- [ ] 8.5 Build context, mature outcomes and project approved memory in order.
- [ ] 8.6 Persist truthful `SUCCESS|PARTIAL|FAILED` evidence and prove retry/idempotency.

## 9. Queue operations and package — #339, #344, #340

- [ ] 9.1 Add queue health, prune and checkpoint commands.
- [ ] 9.2 Gate claims on supported schema and successful integrity checks.
- [ ] 9.3 Preserve bounded terminal evidence for retained maintenance runs before pruning.
- [ ] 9.4 Package queue paths, permissions, one provisioner daemon and maintenance producer timer.
- [ ] 9.5 Add queue migration, backup/restore and upgrade/rollback validation.
- [ ] 9.6 Update architecture, pipeline, deployment and operator documentation.
- [ ] 9.7 Add consistency checks for obsolete no-queue/one-shot guidance.

## 10. Independent installer evidence — #279

- [ ] 10.1 Attach exact-head fresh-install, upgrade and rollback evidence for the previously delivered installer without adding queue-runtime scope.

## 11. Program proof — #255, #317, #306

- [ ] 11.1 Run ten consecutive market sessions on the supported installed host.
- [ ] 11.2 Prove same-date reuse, next-session tails, shared-job joining, priority and worker recovery.
- [ ] 11.3 Prove one finalization per session and truthful partial/failure outcomes.
- [ ] 11.4 Run focused tests, full repository gates and OpenSpec validation on exact SHAs.
- [ ] 11.5 Close #317 only after required child issues and #255 evidence are complete.
- [ ] 11.6 Keep optional #327 datasets outside the #306 core readiness gate.
