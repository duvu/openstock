# Tasks: Symbol Knowledge Memory and Compaction

## 0. Governance and boundaries

- [ ] 0.1 Preserve the read-only research boundary; do not add broker, order, account, portfolio, allocation, margin, transfer, or trading-execution behavior. [evidence: policy regression tests]
- [ ] 0.2 Treat Markdown memory as untrusted historical reference data, never as executable instruction or policy. [evidence: prompt-injection tests]
- [ ] 0.3 Do not store full chat transcripts or raw assistant prose as durable factual memory. [evidence: persistence tests]
- [ ] 0.4 Require source references and temporal metadata for factual and numeric claims. [evidence: claim validation tests]
- [ ] 0.5 Preserve audit history when active information is corrected, expired, superseded, or rejected. [evidence: lifecycle tests]
- [ ] 0.6 Document accepted dependencies and implementation slices before runtime work begins. [evidence: PR description and design review]

## 1. Domain contracts

- [ ] 1.1 Add typed `MemoryEvent` contract. [files: symbol-memory models/contracts] [evidence: serialization tests]
- [ ] 1.2 Add typed `MemoryClaim` contract with claim type, predicate, value, status, confidence, temporal fields, origin, source refs, and correlation ID. [evidence: model tests]
- [ ] 1.3 Add claim statuses: `active`, `superseded`, `expired`, `rejected`, `conflicted`, and pinned state. [evidence: enum/validation tests]
- [ ] 1.4 Add `MemoryDocument` contract with path, schema version, generation, hashes, token estimate, and compaction timestamps. [evidence: model tests]
- [ ] 1.5 Add `MemoryCompactionRun` result and persistence contract. [evidence: model/repository tests]
- [ ] 1.6 Add `MemoryRetrievalResult` with selected claims, omitted-reason metadata, token estimate, as-of date, and source coverage. [evidence: retrieval contract tests]
- [ ] 1.7 Define normalized symbol parsing and reject traversal, separators, absolute paths, Windows drive paths, and reserved components. [evidence: security tests]

## 2. Persistence and migrations

- [ ] 2.1 Add additive, idempotent migrations for `memory_event`. [depends: 1.1] [evidence: fresh and upgrade migration tests]
- [ ] 2.2 Add additive, idempotent migrations for `memory_claim`. [depends: 1.2] [evidence: fresh and upgrade migration tests]
- [ ] 2.3 Add migrations for `memory_document` and `memory_compaction_run`. [depends: 1.4, 1.5] [evidence: migration tests]
- [ ] 2.4 Add repository APIs for append-only memory events. [depends: 2.1] [evidence: repository tests]
- [ ] 2.5 Add repository APIs for claim creation, transition, lookup, conflict, and supersession. [depends: 2.2] [evidence: repository tests]
- [ ] 2.6 Add repository APIs for document metadata and compaction runs. [depends: 2.3] [evidence: repository tests]
- [ ] 2.7 Ensure memory schema failure degrades to a structured unavailable state without crashing the TUI or unrelated research commands. [evidence: legacy database and failure-injection tests]
- [ ] 2.8 Make the index rebuildable from canonical events, claims, and valid document manifests. [evidence: rebuild integration test]

## 3. Canonical filesystem and Markdown documents

- [ ] 3.1 Resolve a canonical knowledge root from the accepted OpenStock user-state root. [evidence: explicit/env/platform precedence tests]
- [ ] 3.2 Add canonical layout `knowledge/symbols/<SYMBOL>.md`, archive, quarantine, manifests, and exports. [depends: 1.7] [evidence: layout tests]
- [ ] 3.3 Define and validate versioned Markdown frontmatter. [evidence: parser/golden tests]
- [ ] 3.4 Implement managed-region parsing and rendering. [evidence: round-trip tests]
- [ ] 3.5 Implement user-region preservation without automated rewriting. [evidence: byte-preservation tests]
- [ ] 3.6 Add managed-content and full-document hashes with generation tracking. [evidence: external-edit tests]
- [ ] 3.7 Write symbol cards through same-directory temporary files, flush, validation, atomic replace, and directory synchronization. [evidence: atomicity/failure tests]
- [ ] 3.8 Detect external edits and record `DOCUMENT_EXTERNALLY_MODIFIED`. [evidence: edit-detection test]
- [ ] 3.9 Quarantine malformed or unrecoverable documents rather than silently overwriting them. [evidence: quarantine tests]

## 4. Memory ingestion and eligibility

- [ ] 4.1 Add an ingestion service that accepts persisted evidence references rather than raw model prose. [depends: 1.1, 2.4] [evidence: eligibility tests]
- [ ] 4.2 Add explicit `/memory remember` user-note ingestion with unverified origin. [evidence: command and persistence tests]
- [ ] 4.3 Add adapter for candidate score snapshots. [evidence: adapter tests]
- [ ] 4.4 Add adapter for feature snapshots and data-quality caveats. [evidence: adapter tests]
- [ ] 4.5 Add adapter for validated market/sector snapshot references when present. [evidence: adapter tests]
- [ ] 4.6 Add adapter for validated deep-symbol analysis artifacts without coupling the memory core to unfinished engine internals. [depends: deep-symbol artifact contract] [evidence: integration tests]
- [ ] 4.7 Add adapter for validated research automation artifacts. [evidence: artifact eligibility tests]
- [ ] 4.8 Reject unsupported numeric claims, missing source references, invalid symbol/date metadata, and raw unvalidated assistant prose. [evidence: negative tests]
- [ ] 4.9 Deduplicate events by stable content hash and evidence identity. [evidence: idempotent ingestion tests]

## 5. Claim lifecycle, correction, and conflict

- [ ] 5.1 Define deterministic source-authority policy by claim type. [depends: 1.2] [evidence: policy matrix tests]
- [ ] 5.2 Implement equivalent-claim merge without duplicate active claims. [evidence: merge tests]
- [ ] 5.3 Implement source-grounded supersession for matching entity and predicate. [evidence: old-to-new transition tests]
- [ ] 5.4 Implement type-specific expiry policies; do not use one global TTL. [evidence: expiry matrix tests]
- [ ] 5.5 Preserve rejected hypotheses needed for recurrence prevention. [evidence: rejected-hypothesis retention tests]
- [ ] 5.6 Detect unresolved same-authority conflicts and preserve both claims. [evidence: conflict tests]
- [ ] 5.7 Add explicit user correction/rejection flow that records an event and lifecycle reason. [evidence: command and repository tests]
- [ ] 5.8 Ensure user correction cannot silently rewrite canonical warehouse evidence. [evidence: authority-boundary tests]
- [ ] 5.9 Invalidate active claims when all supporting sources become invalid and record the transition. [evidence: source invalidation tests]
- [ ] 5.10 Exclude superseded, expired, and rejected claims from the default active card while retaining audit access. [evidence: rendering/retrieval tests]

## 6. Compaction

- [ ] 6.1 Add configurable symbol-card token budget and uncompacted-event thresholds. [evidence: config tests]
- [ ] 6.2 Implement micro-compaction for deduplication, supersession, expiry, and recent-change maintenance. [depends: 5.2–5.5] [evidence: focused compaction tests]
- [ ] 6.3 Implement macro-compaction from canonical structured claims, not prior summary text alone. [depends: 3.4, 5.1–5.10] [evidence: source-of-truth tests]
- [ ] 6.4 Preserve pinned claims, user regions, active risks, conflicts, open questions, and important rejected hypotheses. [evidence: preservation tests]
- [ ] 6.5 Produce dry-run retained/archive/conflict counts, source coverage, token estimates, and proposed diff. [evidence: dry-run command tests]
- [ ] 6.6 Ensure dry-run performs no mutation. [evidence: hash/database immutability test]
- [ ] 6.7 Persist compaction manifests with before/after generations and hashes. [evidence: manifest tests]
- [ ] 6.8 Rotate and compress eligible archive events without deleting referenced evidence. [evidence: archive and reference-retention tests]
- [ ] 6.9 Prove repeated compaction without new input is idempotent and creates no duplicate archive entries. [evidence: repeated-run test]
- [ ] 6.10 Add scheduled maintenance entry point with bounded work and failure isolation per symbol. [evidence: scheduler/service tests]

## 7. Retrieval and context construction

- [ ] 7.1 Implement exact symbol retrieval before optional lexical or semantic ranking. [depends: 2.5] [evidence: retrieval tests]
- [ ] 7.2 Enforce as-of filtering using claim date, source publication date when known, and validity window. [evidence: no-lookahead tests]
- [ ] 7.3 Exclude expired, superseded, and rejected claims by default. [evidence: status-filter tests]
- [ ] 7.4 Include conflict metadata, risks, caveats, and missing data when relevant. [evidence: retrieval tests]
- [ ] 7.5 Add configurable total memory context budget and per-section allocation. [evidence: budget tests]
- [ ] 7.6 Select claims atomically as whole units; do not truncate claims mid-record. [evidence: tight-budget tests]
- [ ] 7.7 Mark memory context as untrusted and subordinate to current policy and validated tool output. [evidence: prompt contract tests]
- [ ] 7.8 Add retrieval metadata for selected and omitted claims, token estimate, freshness, and source coverage. [evidence: result contract tests]
- [ ] 7.9 Prove archive growth does not increase configured prompt budget. [evidence: scale test]

## 8. Command and TUI surface

- [ ] 8.1 Register `/memory` in the unified command catalog. [evidence: registry/help tests]
- [ ] 8.2 Implement `/memory status`. [evidence: command tests]
- [ ] 8.3 Implement `/memory show SYMBOL`. [evidence: command tests]
- [ ] 8.4 Implement `/memory remember SYMBOL "note"`. [evidence: command tests]
- [ ] 8.5 Implement `/memory correct SYMBOL <claim-id> "correction"`. [evidence: command tests]
- [ ] 8.6 Implement pin/unpin behavior. [evidence: command tests]
- [ ] 8.7 Implement conflict and source inspection. [evidence: command tests]
- [ ] 8.8 Implement compact dry-run and execute modes. [evidence: mutation-boundary tests]
- [ ] 8.9 Implement repair and rebuild-index commands. [evidence: recovery tests]
- [ ] 8.10 Render memory availability, conflicts, freshness, and compaction state without exposing raw sensitive note bodies in status or logs. [evidence: TUI snapshot/redaction tests]

## 9. Concurrency, recovery, and observability

- [ ] 9.1 Add symbol-scoped locking so independent symbols can update concurrently. [evidence: multi-process tests]
- [ ] 9.2 Add root maintenance lock for bulk compaction and index rebuild. [evidence: contention tests]
- [ ] 9.3 Ensure event/claim transaction and Markdown generation cannot produce an unindexed or partially written active document. [evidence: crash/failure injection tests]
- [ ] 9.4 Add repair flow for hash, marker, frontmatter, index, and claim-reference inconsistencies. [evidence: repair tests]
- [ ] 9.5 Emit bounded, redacted memory lifecycle events with correlation IDs. [evidence: observability tests]
- [ ] 9.6 Record claim counts, statuses, hashes, token estimates, source coverage, and durations without logging raw note content. [evidence: redaction tests]

## 10. Evaluation and regression tests

- [ ] 10.1 Test newer authoritative evidence removes a stale claim from the active card while preserving history.
- [ ] 10.2 Test unsupported numeric information is rejected.
- [ ] 10.3 Test same-authority conflict remains unresolved and visible.
- [ ] 10.4 Test future evidence is excluded from historical retrieval.
- [ ] 10.5 Test user note is not promoted as verified fact.
- [ ] 10.6 Test user block survives compaction byte-for-byte.
- [ ] 10.7 Test prompt injection inside Markdown cannot alter classification, planning, policy, or tool selection.
- [ ] 10.8 Test corrupt Markdown is quarantined and the application remains usable.
- [ ] 10.9 Test two concurrent writers do not lose events or corrupt the symbol card.
- [ ] 10.10 Test 10,000 archived events do not increase retrieval beyond the configured budget.
- [ ] 10.11 Test migration from every supported prior warehouse schema.
- [ ] 10.12 Add runtime evaluation corpus for correction, conflict, compaction, temporal filtering, and source grounding.

## 11. Documentation and validation

- [ ] 11.1 Document storage layout, Markdown schema, managed/user regions, and manual-edit policy.
- [ ] 11.2 Document claim types, lifecycle states, source authority, expiry, correction, and conflict semantics.
- [ ] 11.3 Document compaction triggers, dry-run behavior, archive retention, and recovery.
- [ ] 11.4 Document context budgets and no-lookahead guarantees.
- [ ] 11.5 Document operator migration, repair, and index rebuild procedures.
- [ ] 11.6 Run `make repo-hygiene`. [evidence: command log]
- [ ] 11.7 Run `make lint-vnalpha`. [evidence: command log]
- [ ] 11.8 Run focused symbol-memory tests. [evidence: test log]
- [ ] 11.9 Run `make test-vnalpha`. [evidence: command log]
- [ ] 11.10 Run `make verify-r4`. [evidence: command log]
- [ ] 11.11 Run `packaging/scripts/openstock-verify --ci`. [evidence: command log]
- [ ] 11.12 Attach exact validation evidence to the implementation PR before checking phase gates.

## Phase gates

- [ ] G1 Domain, migrations, canonical paths, and explicit user-note workflow pass.
- [ ] G2 Claim authority, correction, conflict, and temporal lifecycle pass.
- [ ] G3 Compaction, archive, atomicity, and recovery pass.
- [ ] G4 Retrieval budgets, no-lookahead, and prompt trust pass.
- [ ] G5 Command/TUI surface and repository-wide regression gates pass.