# Tasks: Symbol Knowledge Memory and Compaction

## 0. Governance and boundaries

- [x] 0.1 Preserve the read-only research boundary; do not add broker, order, account, portfolio, allocation, margin, transfer, or trading-execution behavior. [evidence: `vnalpha/tests/test_safety_boundary.py`]
- [x] 0.2 Treat Markdown memory as untrusted historical reference data, never as executable instruction or policy. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`, `vnalpha/src/vnalpha/evals/runtime_cases/symbol_memory_context_injection.json`]
- [x] 0.3 Do not store full chat transcripts or raw assistant prose as durable factual memory. [evidence: `vnalpha/tests/test_symbol_memory_boundaries.py`]
- [x] 0.4 Require source references and temporal metadata for factual and numeric claims. [evidence: `vnalpha/tests/test_symbol_memory_models.py`]
- [x] 0.5 Preserve audit history when active information is corrected, expired, superseded, or rejected. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 0.6 Document accepted dependencies and implementation slices before runtime work begins. [evidence: `openspec/changes/symbol-knowledge-memory/design.md`]

## 1. Domain contracts

- [x] 1.1 Add typed `MemoryEvent` contract. [files: `vnalpha/src/vnalpha/symbol_memory/models.py`] [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 1.2 Add typed `MemoryClaim` contract with claim type, predicate, value, status, confidence, temporal fields, origin, source refs, and correlation ID. [evidence: `vnalpha/tests/test_symbol_memory_models.py`]
- [x] 1.3 Add claim statuses: `active`, `superseded`, `expired`, `rejected`, `conflicted`, and pinned state. [evidence: `vnalpha/tests/test_symbol_memory_models.py`]
- [x] 1.4 Add `MemoryDocument` contract with path, schema version, generation, hashes, token estimate, and compaction timestamps. [evidence: `vnalpha/tests/test_symbol_memory_models.py`]
- [x] 1.5 Add `MemoryCompactionRun` result and persistence contract. [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 1.6 Add `MemoryRetrievalResult` with selected claims, omitted-reason metadata, token estimate, as-of date, and source coverage. [evidence: `vnalpha/tests/test_symbol_memory_models.py`]
- [x] 1.7 Define normalized symbol parsing and reject traversal, separators, absolute paths, Windows drive paths, and reserved components. [evidence: `vnalpha/tests/test_symbol_memory_models.py`]

## 2. Persistence and migrations

- [x] 2.1 Add additive, idempotent migrations for `memory_event`. [depends: 1.1] [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 2.2 Add additive, idempotent migrations for `memory_claim`. [depends: 1.2] [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 2.3 Add migrations for `memory_document` and `memory_compaction_run`. [depends: 1.4, 1.5] [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 2.4 Add repository APIs for append-only memory events. [depends: 2.1] [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 2.5 Add repository APIs for claim creation, transition, lookup, conflict, and supersession. [depends: 2.2] [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 2.6 Add repository APIs for document metadata and compaction runs. [depends: 2.3] [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 2.7 Ensure memory schema failure degrades to a structured unavailable state without crashing the TUI or unrelated research commands. [evidence: `vnalpha/tests/test_symbol_memory_availability.py`]
- [x] 2.8 Make the index rebuildable from canonical events, claims, and valid document manifests. [evidence: `vnalpha/tests/test_symbol_memory_availability.py`]

## 3. Canonical filesystem and Markdown documents

- [x] 3.1 Resolve a canonical knowledge root from the accepted OpenStock user-state root. [evidence: `vnalpha/tests/test_symbol_memory_markdown.py`]
- [x] 3.2 Add canonical layout `knowledge/symbols/<SYMBOL>.md`, archive, quarantine, manifests, and exports. [depends: 1.7] [evidence: `vnalpha/tests/test_symbol_memory_markdown.py`]
- [x] 3.3 Define and validate versioned Markdown frontmatter. [evidence: `vnalpha/tests/test_symbol_memory_markdown.py`]
- [x] 3.4 Implement managed-region parsing and rendering. [evidence: `vnalpha/tests/test_symbol_memory_markdown.py`]
- [x] 3.5 Implement user-region preservation without automated rewriting. [evidence: `vnalpha/tests/test_symbol_memory_markdown.py`]
- [x] 3.6 Add managed-content and full-document hashes with generation tracking. [evidence: `vnalpha/tests/test_symbol_memory_markdown.py`]
- [x] 3.7 Write symbol cards through same-directory temporary files, flush, validation, atomic replace, and directory synchronization. [evidence: `vnalpha/tests/test_symbol_memory_markdown.py`]
- [x] 3.8 Detect external edits and record `DOCUMENT_EXTERNALLY_MODIFIED`. [evidence: `vnalpha/tests/test_symbol_memory_recovery.py`]
- [x] 3.9 Quarantine malformed or unrecoverable documents rather than silently overwriting them. [evidence: `vnalpha/tests/test_symbol_memory_recovery.py`]

## 4. Memory ingestion and eligibility

- [x] 4.1 Add an ingestion service that accepts persisted evidence references rather than raw model prose. [depends: 1.1, 2.4] [evidence: `vnalpha/tests/test_symbol_memory_ingestion.py`]
- [x] 4.2 Add explicit `/memory remember` user-note ingestion with unverified origin. [evidence: `vnalpha/tests/test_symbol_memory_ingestion.py`]
- [x] 4.3 Add adapter for candidate score snapshots. [evidence: `vnalpha/tests/test_symbol_memory_adapters.py`]
- [x] 4.4 Add adapter for feature snapshots and data-quality caveats. [evidence: `vnalpha/tests/test_symbol_memory_adapters.py`]
- [x] 4.5 Add adapter for validated market/sector snapshot references when present. [evidence: `vnalpha/tests/test_symbol_memory_adapters.py`]
- [x] 4.6 Add adapter for validated deep-symbol analysis artifacts without coupling the memory core to unfinished engine internals. [depends: deep-symbol artifact contract] [evidence: `vnalpha/tests/test_symbol_memory_adapters.py`]
- [x] 4.7 Add adapter for validated research automation artifacts. [evidence: `vnalpha/tests/test_symbol_memory_adapters.py`]
- [x] 4.8 Reject unsupported numeric claims, missing source references, invalid symbol/date metadata, and raw unvalidated assistant prose. [evidence: `vnalpha/tests/test_symbol_memory_ingestion.py`]
- [x] 4.9 Deduplicate events by stable content hash and evidence identity. [evidence: `vnalpha/tests/test_symbol_memory_ingestion.py`]

## 5. Claim lifecycle, correction, and conflict

- [x] 5.1 Define deterministic source-authority policy by claim type. [depends: 1.2] [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.2 Implement equivalent-claim merge without duplicate active claims. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.3 Implement source-grounded supersession for matching entity and predicate. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.4 Implement type-specific expiry policies; do not use one global TTL. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.5 Preserve rejected hypotheses needed for recurrence prevention. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.6 Detect unresolved same-authority conflicts and preserve both claims. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.7 Add explicit user correction/rejection flow that records an event and lifecycle reason. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.8 Ensure user correction cannot silently rewrite canonical warehouse evidence. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.9 Invalidate active claims when all supporting sources become invalid and record the transition. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 5.10 Exclude superseded, expired, and rejected claims from the default active card while retaining audit access. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`, `vnalpha/tests/test_symbol_memory_compaction.py`]

## 6. Compaction

- [x] 6.1 Add configurable symbol-card token budget and uncompacted-event thresholds. [evidence: `vnalpha/tests/test_symbol_memory_maintenance.py`]
- [x] 6.2 Implement micro-compaction for deduplication, supersession, expiry, and recent-change maintenance. [depends: 5.2–5.5] [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 6.3 Implement macro-compaction from canonical structured claims, not prior summary text alone. [depends: 3.4, 5.1–5.10] [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 6.4 Preserve pinned claims, user regions, active risks, conflicts, open questions, and important rejected hypotheses. [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 6.5 Produce dry-run retained/archive/conflict counts, source coverage, token estimates, and proposed diff. [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 6.6 Ensure dry-run performs no mutation. [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 6.7 Persist compaction manifests with before/after generations and hashes. [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 6.8 Rotate and compress eligible archive events without deleting referenced evidence. [evidence: `vnalpha/tests/test_symbol_memory_maintenance.py`]
- [x] 6.9 Prove repeated compaction without new input is idempotent and creates no duplicate archive entries. [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 6.10 Add scheduled maintenance entry point with bounded work and failure isolation per symbol. [evidence: `vnalpha/tests/test_symbol_memory_maintenance.py`]

## 7. Retrieval and context construction

- [x] 7.1 Implement exact symbol retrieval before optional lexical or semantic ranking. [depends: 2.5] [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 7.2 Enforce as-of filtering using claim date, source publication date when known, and validity window. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 7.3 Exclude expired, superseded, and rejected claims by default. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 7.4 Include conflict metadata, risks, caveats, and missing data when relevant. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 7.5 Add configurable total memory context budget and per-section allocation. [evidence: `vnalpha/tests/test_symbol_memory_maintenance.py`]
- [x] 7.6 Select claims atomically as whole units; do not truncate claims mid-record. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 7.7 Mark memory context as untrusted and subordinate to current policy and validated tool output. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 7.8 Add retrieval metadata for selected and omitted claims, token estimate, freshness, and source coverage. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 7.9 Prove archive growth does not increase configured prompt budget. [evidence: `vnalpha/tests/test_symbol_memory_maintenance.py`]

## 8. Command and TUI surface

- [x] 8.1 Register `/memory` in the unified command catalog. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.2 Implement `/memory status`. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.3 Implement `/memory show SYMBOL`. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.4 Implement `/memory remember SYMBOL "note"`. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.5 Implement `/memory correct SYMBOL <claim-id> "correction"`. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.6 Implement pin/unpin behavior. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.7 Implement conflict and source inspection. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.8 Implement compact dry-run and execute modes. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.9 Implement repair and rebuild-index commands. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`]
- [x] 8.10 Render memory availability, conflicts, freshness, and compaction state without exposing raw sensitive note bodies in status or logs. [evidence: `vnalpha/tests/test_symbol_memory_commands.py`, `vnalpha/tests/test_symbol_memory_observability.py`]

## 9. Concurrency, recovery, and observability

- [x] 9.1 Add symbol-scoped locking so independent symbols can update concurrently. [evidence: `vnalpha/tests/test_symbol_memory_locking.py`]
- [x] 9.2 Add root maintenance lock for bulk compaction and index rebuild. [evidence: `vnalpha/tests/test_symbol_memory_locking.py`]
- [x] 9.3 Ensure event/claim transaction and Markdown generation cannot produce an unindexed or partially written active document. [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 9.4 Add repair flow for hash, marker, frontmatter, index, and claim-reference inconsistencies. [evidence: `vnalpha/tests/test_symbol_memory_recovery.py`]
- [x] 9.5 Emit bounded, redacted memory lifecycle events with correlation IDs. [evidence: `vnalpha/tests/test_symbol_memory_observability.py`]
- [x] 9.6 Record claim counts, statuses, hashes, token estimates, source coverage, and durations without logging raw note content. [evidence: `vnalpha/tests/test_symbol_memory_observability.py`]

## 10. Evaluation and regression tests

- [x] 10.1 Test newer authoritative evidence removes a stale claim from the active card while preserving history. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`]
- [x] 10.2 Test unsupported numeric information is rejected. [evidence: `vnalpha/tests/test_symbol_memory_ingestion.py`]
- [x] 10.3 Test same-authority conflict remains unresolved and visible. [evidence: `vnalpha/tests/test_symbol_memory_lifecycle.py`, `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 10.4 Test future evidence is excluded from historical retrieval. [evidence: `vnalpha/tests/test_symbol_memory_retrieval.py`]
- [x] 10.5 Test user note is not promoted as verified fact. [evidence: `vnalpha/tests/test_symbol_memory_ingestion.py`]
- [x] 10.6 Test user block survives compaction byte-for-byte. [evidence: `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 10.7 Test prompt injection inside Markdown cannot alter classification, planning, policy, or tool selection. [evidence: `vnalpha/src/vnalpha/evals/runtime_cases/symbol_memory_context_injection.json`]
- [x] 10.8 Test corrupt Markdown is quarantined and the application remains usable. [evidence: `vnalpha/tests/test_symbol_memory_recovery.py`]
- [x] 10.9 Test two concurrent writers do not lose events or corrupt the symbol card. [evidence: `vnalpha/tests/test_symbol_memory_locking.py`, `vnalpha/tests/test_symbol_memory_compaction.py`]
- [x] 10.10 Test 10,000 archived events do not increase retrieval beyond the configured budget. [evidence: `vnalpha/tests/test_symbol_memory_maintenance.py`]
- [x] 10.11 Test migration from every supported prior warehouse schema. [evidence: `vnalpha/tests/test_symbol_memory_repository.py`]
- [x] 10.12 Add runtime evaluation corpus for correction, conflict, compaction, temporal filtering, and source grounding. [evidence: `vnalpha/src/vnalpha/evals/runtime_cases/symbol_memory_{correction,conflict,compaction,temporal_filtering,source_grounding}.json`, runtime replay corpus]

## 11. Documentation and validation

- [x] 11.1 Document storage layout, Markdown schema, managed/user regions, and manual-edit policy. [evidence: `vnalpha/docs/symbol-memory.md`]
- [x] 11.2 Document claim types, lifecycle states, source authority, expiry, correction, and conflict semantics. [evidence: `vnalpha/docs/symbol-memory.md`]
- [x] 11.3 Document compaction triggers, dry-run behavior, archive retention, and recovery. [evidence: `vnalpha/docs/symbol-memory.md`]
- [x] 11.4 Document context budgets and no-lookahead guarantees. [evidence: `vnalpha/docs/symbol-memory.md`]
- [x] 11.5 Document operator migration, repair, and index rebuild procedures. [evidence: `vnalpha/docs/symbol-memory.md`]
- [x] 11.6 Run `make repo-hygiene`. [evidence: command log, 2026-07-13]
- [x] 11.7 Run `make lint-vnalpha`. [evidence: command log, 2026-07-13]
- [x] 11.8 Run focused symbol-memory tests. [evidence: test log, 2026-07-13]
- [x] 11.9 Run `make test-vnalpha`. [evidence: command log, 2026-07-13]
- [x] 11.10 Run `make verify-r4`. [evidence: command log, 2026-07-13]
- [x] 11.11 Run `packaging/scripts/openstock-verify --ci`. [evidence: command log, 2026-07-13]
- [x] 11.12 Attach exact validation evidence to the implementation PR before checking phase gates. [evidence: draft PR #71, exact implementation SHA `3af296419b04155e4aee16d45258f6d458fd8ba2`]

## 12. Daily selective and typed entity memory

- [x] 12.1 Project only material validated candidate/taxonomy changes after daily maintenance and expose lifecycle counters. [evidence: `vnalpha/tests/test_issue_240_selective_symbol_memory.py`]
- [x] 12.2 Add allowlisted SYMBOL, MARKET, SECTOR, INDUSTRY and ASSET_CLASS identity across repository, lifecycle, retrieval and compaction with symbol compatibility wrappers. [evidence: `vnalpha/tests/test_issue_241_entity_memory.py`]
- [x] 12.3 Persist deterministic point-in-time group snapshots using the production sector metrics and project only changed validated context. [evidence: `vnalpha/tests/test_issue_242_group_context_memory.py`]
- [x] 12.4 Retrieve market/group context alongside symbol context under one total token budget. [evidence: `vnalpha/tests/test_issue_242_group_context_memory.py`]
- [x] 12.5 Prove migration of populated legacy event, claim, document and compaction tables without loss. [evidence: `vnalpha/tests/test_issue_241_entity_memory.py`]
- [ ] 12.6 Run exact-candidate full gates and reconcile issues #240-#242.

## Phase gates

- [x] G1 Domain, migrations, canonical paths, and explicit user-note workflow pass. [evidence: 35 focused tests on `3af2964`; draft PR #71]
- [x] G2 Claim authority, correction, conflict, and temporal lifecycle pass. [evidence: 21 focused tests on `3af2964`; draft PR #71]
- [x] G3 Compaction, archive, atomicity, and recovery pass. [evidence: 19 focused tests on `3af2964`; draft PR #71]
- [x] G4 Retrieval budgets, no-lookahead, and prompt trust pass. [evidence: 16 focused tests and five runtime replay cases on `3af2964`; draft PR #71]
- [x] G5 Command/TUI surface and repository-wide regression gates pass. [evidence: manual command QA, lint, full vnalpha suite, R4, packaging, and strict OpenSpec validation on `3af2964`; draft PR #71]
