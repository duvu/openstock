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
- [x] 2.4 Add versioned models for `ENSURE_CURRENT_SYMBOL`, `SYNC_DATASET_RANGE` and `FINALIZE_MARKET_SESSION`. Evidence: `9a6f516843eda890bd5d13e9bbfc4a7612e2eecc`, hardened by `d09efd351c9297c91bda18355b13979c02635036`, `e423e585646b4676dc7034430861e741a5abe1c8` and `0b3fef7bc820d2995bbbafe2ee49fb99d87cfe88`; supported source-policy and contract versions fail closed before queue persistence or handler execution, proven by the goal and queue contract tests.
- [x] 2.5 Add deterministic identities, enrichment normalization and collision tests. Evidence: `d09efd351c9297c91bda18355b13979c02635036`; authoritative `vnalpha/tests/test_provisioning_queue_goals.py::test_provisioning_goal_contract`; `make test-loop TEST=tests/test_provisioning_queue_goals.py::test_provisioning_goal_contract` passed; `uv run python ../scripts/run_test_suite.py --plan --domain application` validates the authoritative inventory.

## 3. Queue repository — #323

- [x] 3.1 Add SQLite schema, migrations and explicit WAL/busy-timeout settings. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820`, separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`, and boundary-corrected by `7729b21e9d4d52d64390d4ffea29b8f5e24c2bb1`.
- [x] 3.2 Implement submit-or-join with priority escalation. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`.
- [x] 3.3 Implement atomic claim, lease, heartbeat and bounded retry. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`.
- [x] 3.4 Implement status, terminal result, cancellation and size limits. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`.
- [x] 3.5 Prove concurrent submit/claim/status behavior without DuckDB access. Evidence: `3726ac8a8dad484084e493765be02849f8fe4a84`, hardened by `5797cca25482ffb0d5a62e86c4531eb0fb8b2820` and separated by `ecc729c9f569a5e09a66688cee4cb55c8d5f6a84`; authoritative `vnalpha/tests/test_provisioning_queue_repository.py::test_durable_provisioning_queue_contract`; `make test-loop TEST=tests/test_provisioning_queue_repository.py::test_durable_provisioning_queue_contract` passed; `uv run python ../scripts/run-test-suite.py --plan --domain application` validates the authoritative inventory.

## 4. Sequential worker — #324

- [x] 4.1 Add one worker and explicit handler registry. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`, hardened by `079c32dfa3d59fd9bb345d5b730a0112035c2d45`, `031aef766584d14493b3835dc65baf69705098e3` and `555a7b772e4a0d47edc4f4248b8bc7e185c42b06`; the provisioner flocks the initialized shared queue inode across path aliases. Authoritative: `vnalpha/tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract`.
- [x] 4.2 Open writable DuckDB only through #343 after lock acquisition. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`; the worker injects `WarehouseWriteCoordinator` and the contract verifies an unregistered goal creates no warehouse file.
- [x] 4.3 Re-read and re-plan after claim. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`, hardened by `079c32dfa3d59fd9bb345d5b730a0112035c2d45`; the current-symbol handler delegates core price/ranking work to the existing current-symbol operation and the restart contract proves persisted effects are reused. Enrichment and source-policy execution remain with their owning changes.
- [x] 4.4 Add bounded stage timeouts, lease extension and cooperative stop behavior. Evidence: `1b3d36a87769702aed93af10f08e819c9aa28704` gives each handler a finite stage sequence, maintains the active lease during each stage, fails timeout only after its transaction boundary, rolls back an interrupted active stage, acknowledges cancellation before the next stage, and leaves a SIGTERM-interrupted job recoverable without claiming the next job. Authoritative: `vnalpha/tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract`; `make test-loop TEST=tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract` passed.
- [x] 4.5 Prove retry after process interruption creates no duplicate persisted artifacts. Evidence: `21c53513663a960d7334606bd035fcd4c4f9f016`, hardened by `079c32dfa3d59fd9bb345d5b730a0112035c2d45`; `make test-loop TEST=tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract` passed with committed-effect/expired-lease restart reuse and an active-stage lease-overrun probe.

## 5. Provisioning behavior — #318, #319, #321

- [x] 5.1 Ready same-date requests return without a queue job or write work. Evidence: `vnalpha/tests/test_current_symbol_research_application.py::test_ready_current_symbol_reuses_persisted_evidence_without_a_queue_job`; `make test-loop TEST=tests/test_current_symbol_research_application.py::test_ready_current_symbol_reuses_persisted_evidence_without_a_queue_job` passed.
- [x] 5.2 Compute exact missing OHLCV tails and bounded repair ranges. Evidence: `vnalpha/tests/test_data_only_symbol.py::test_stale_raw_evidence_syncs_only_the_missing_session_tail`; `make test-loop TEST=tests/test_data_only_symbol.py::test_stale_raw_evidence_syncs_only_the_missing_session_tail` passed.
- [x] 5.3 Avoid provider calls when raw evidence is ready and canonical evidence is stale. Evidence: `vnalpha/tests/test_data_only_symbol.py::test_raw_ready_canonical_stale_promotes_only_the_missing_tail`; `make test-loop TEST=tests/test_data_only_symbol.py::test_raw_ready_canonical_stale_promotes_only_the_missing_tail` passed.
- [x] 5.4 Add date-bounded canonical promotion. Evidence: `vnalpha/tests/test_canonical_quarantine.py::test_bounded_canonical_promotion_leaves_outside_dates_unchanged`; `make test-loop TEST=tests/test_canonical_quarantine.py::test_bounded_canonical_promotion_leaves_outside_dates_unchanged` passed.
- [x] 5.5 Stop dependent actions after the first failed prerequisite and record `BLOCKED`. Evidence: `vnalpha/tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract`; `make test-loop TEST=tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract` passed.
- [x] 5.6 Add row-count, function-call and same-date idempotency tests. Evidence: `vnalpha/tests/test_current_symbol_research_application.py::test_ready_current_symbol_reuses_persisted_evidence_without_a_queue_job` verifies unchanged canonical row count and no queue creation for same-date ready evidence; `make test-loop TEST=tests/test_current_symbol_research_application.py::test_ready_current_symbol_reuses_persisted_evidence_without_a_queue_job` passed.

## 6. Interactive application — #325, #322

- [x] 6.1 Add queue client operations without holding DuckDB while waiting. Evidence: `CurrentSymbolResearchApplication` closes its readiness inspection before queue initialization/submission; `vnalpha/tests/test_current_symbol_research_application.py::test_missing_current_symbol_work_joins_one_escalated_queue_job` passed.
- [x] 6.2 Implement shared `WAIT_UNTIL_TERMINAL`, `WAIT_UP_TO` and `DETACH` defaults. Evidence: `CurrentSymbolWaitMode` owns the three modes; the application contract covers default detach and zero-duration bounded wait with `make test-loop TEST=tests/test_current_symbol_research_application.py::test_missing_current_symbol_work_joins_one_escalated_queue_job` passing.
- [x] 6.3 Add priority escalation and explicit shared-job cancellation warnings. Evidence: `8fa2f313cdb1a7674fd6b6bb074dfbef153417bd`, hardened by `0ef4237aed1d3fa651411016f1fed7166cc22853`; the current-symbol contract proves active requests share one priority-escalated job, unconfirmed `jobs cancel` preserves it with an explicit shared-job warning, confirmed cancellation is administrative, terminal cancellation returns a bounded diagnostic, and `jobs retry` creates a new typed job.
- [x] 6.4 Add `CurrentSymbolResearchApplication` as the single CLI/TUI/chat boundary. Evidence: `analysis.current_symbol` is registered by `build_local_tool_registry()` and the managed assistant invokes it outside any held warehouse connection.
- [x] 6.5 Replace the assistant's unconditional provision-then-analyze plan with one application operation. Evidence: `tests/test_assistant_research_intelligence_completion.py::test_research_prompt_contains_template_and_bounded_source_refs` asserts one `analysis.current_symbol` plan step.
- [x] 6.6 Enforce `READY|DEGRADED|ACCEPTED|PENDING|UNAVAILABLE|FAILED` and claim limitations. Evidence: terminal missing-capability jobs return `UNAVAILABLE`; non-analysis states return no analysis payload; degraded payloads remove ranking/score/benchmark claims.
- [ ] 6.7 Add cross-surface parity and no-analysis tests for non-analysis states.

## 7. Maintenance producer — #326

- [x] 7.1 Add maintenance states, frozen universe/session/source-policy fields and expected goal identities. Evidence: `MaintenanceProducer` persists the frozen snapshot ID, hash, symbols, calendar and expected goal payloads before submission.
- [x] 7.2 Add idempotent `maintenance_run_job` mapping. Evidence: `maintenance_run_job` uses `(maintenance_run_id, goal_identity)` as its primary key and maps queue IDs only when absent.
- [x] 7.3 Implement phased resume across DuckDB ledger and SQLite queue updates. Evidence: producer submission and mapping are separate phases; resuming an existing run reuses mappings and queue identity without duplicate jobs.
- [x] 7.4 Enqueue VNINDEX as dataset-range work and equities as `PRICE_ANALYSIS` goals. Evidence: `test_maintenance_producer_freezes_goals_and_resumes_idempotently` verifies one benchmark plus one price-only goal per frozen symbol.
- [x] 7.5 Ensure acquisition does not build batch features, scores or watchlists. Evidence: maintenance equity goals request only `ReadinessCapability.PRICE_ANALYSIS`; finalization remains a separate downstream goal.
- [x] 7.6 Return enqueue/detach evidence, never final daily success. Evidence: `MaintenanceProducerResult` reports run state, expected/submitted/joined/mapped counts and job IDs while producer state stops at `ACQUIRING`.

## 8. Session finalization — #337

- [x] 8.1 Add idempotent `maybe_submit_session_finalization()` trigger. Evidence: `vnalpha/tests/test_maintenance_producer.py::test_maintenance_producer_freezes_goals_and_resumes_idempotently` submits one finalization goal after acquisition completion and joins it on repeat.
- [x] 8.2 Guard against unmapped or active expected jobs. Evidence: the same contract returns `ACQUIRING` without submission before acquisition jobs are terminal.
- [x] 8.3 Add the finalization handler and state transitions. Evidence: the registered `FinalizeMarketSessionGoalHandler` moves the frozen run to `FINALIZING`, persists deterministic finalizer stages, and terminal worker jobs automatically invoke the submit-or-join trigger for mapped maintenance acquisition work.
- [x] 8.4 Build features and score/watchlist once for the frozen eligible universe. Evidence: `SessionFinalizer` derives the canonical eligible frozen scope, runs one features stage then one score/watchlist stage, and reuses completed stages on retry.
- [x] 8.5 Build context, mature outcomes and project approved memory in order. Evidence: the handler stage order is context, outcomes, memory after score/watchlist; the maintenance producer contract runs a seeded frozen session through those stages.
- [x] 8.6 Persist truthful `SUCCESS|PARTIAL|FAILED` evidence and prove retry/idempotency. Evidence: the maintenance producer contract proves benchmark/coverage failure persists `FAILED`, a complete frozen session persists `SUCCESS`, 80% frozen coverage persists `PARTIAL`, recovery joins the existing finalization job, and replay preserves exactly seven deterministic finalization-stage rows.

## 9. Queue operations and package — #339, #344, #340

- [x] 9.1 Add queue health, prune and checkpoint commands. Evidence: `vnalpha jobs health`, `jobs checkpoint`, and batch-bounded `jobs prune --older-than DAYS` expose queue state without automatic repair; the durable queue contract and CLI smoke proof passed.
- [x] 9.2 Gate claims on supported schema and successful integrity checks. Evidence: `ProvisioningQueue.claim` rejects the typed queue health gate when the schema is unsupported or integrity inspection fails; the durable queue contract proves the unsupported-schema case.
- [x] 9.3 Preserve bounded terminal evidence for retained maintenance runs before pruning. Evidence: pruning writes a typed SQLite tombstone only for unreferenced terminal jobs and retains every `maintenance_run_job` mapping; the durable queue contract proves prunable, retained, and active rows.
- [x] 9.4 Package queue paths, permissions, one provisioner daemon and maintenance producer timer. Evidence: the package creates `/var/lib/openstock/queue` as `root:openstock` mode `0770`; both config trees select the durable queue path; the opt-in `openstock-provisioner.service` starts exactly one sequential worker; and the existing weekday producer remains an opt-in timer. Source/package unit parity, package contracts, `openstock-verify --ci`, and an offline Debian payload build passed.
- [ ] 9.5 Add queue migration, backup/restore and upgrade/rollback validation.
- [x] 9.6 Update architecture, pipeline, deployment and operator documentation. Evidence: the system architecture, data pipeline, deployment architecture, roadmap, Debian install guide, operator/rollback procedures, live-soak requirements, and root README distinguish the one provisioner daemon from explicit container jobs and document the paired warehouse/queue recovery flow; #238 has a #317 successor note.
- [x] 9.7 Add consistency checks for obsolete no-queue/one-shot guidance. Evidence: `packaging/tests/test_daily_pipeline_units.sh` requires the durable queue/provisioner deployment contract and rejects the obsolete direct `maintain daily` live-soak instruction; `scripts/check-repo-consistency.py` now enforces queue path, daemon, wait-policy, paired recovery, and no-distributed-claim documentation invariants; both checks passed.

## 10. Independent installer evidence — #279

- [ ] 10.1 Attach exact-head fresh-install, upgrade and rollback evidence for the previously delivered installer without adding queue-runtime scope.

## 11. Program proof — #255, #317, #306

- [ ] 11.1 Run ten consecutive market sessions on the supported installed host.
- [ ] 11.2 Prove same-date reuse, next-session tails, shared-job joining, priority and worker recovery.
- [ ] 11.3 Prove one finalization per session and truthful partial/failure outcomes.
- [ ] 11.4 Run focused tests, full repository gates and OpenSpec validation on exact SHAs.
- [ ] 11.5 Close #317 only after required child issues and #255 evidence are complete.
- [ ] 11.6 Keep optional #327 datasets outside the #306 core readiness gate.
