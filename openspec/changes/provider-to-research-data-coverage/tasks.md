# Tasks: Provider-to-research data coverage

A task is complete only when the named contract, implementation, focused tests and exact-SHA evidence exist.

## 1. Capability inventory — #328

- [x] 1.1 Define the machine-readable inventory schema and finite status vocabulary. [evidence: `vnstock/core/capability_inventory.py`, `vnstock/docs/dataset-capability-inventory.json`]
- [x] 1.2 Add one row for every built-in contract, route and provider capability. [evidence: `vnstock/tests/contracts/test_dataset_capability_inventory.py::test_dataset_capability_inventory_matches_runtime_contracts`]
- [x] 1.3 Record quality, `vnalpha` client/persistence/consumer, point-in-time, license and queue mapping separately. [evidence: `vnstock/docs/dataset-capability-inventory.json`]
- [x] 1.4 Mark `foreign_flow.daily` deferred until #336. [evidence: `foreign_flow.daily` inventory row]
- [x] 1.5 Remove unsupported `fund.holdings` route without creating a placeholder fund product. [evidence: `vnstock/service/dataset_mapper.py`, focused inventory contract test]
- [x] 1.6 Add repository consistency tests for contract/route/provider/client/queue/document drift. [evidence: `vnstock/tests/contracts/test_dataset_capability_inventory.py::test_dataset_capability_inventory_matches_runtime_contracts`]

## 2. Optional current context

### #329 — company profile

- [x] 2.1 Add typed company-info client and verified provider fixture. [evidence: `vnalpha/clients/vnstock/client.py`, `vnalpha/tests/test_company_context.py::test_company_context_preserves_current_revision_contract`]
- [x] 2.2 Persist idempotent current snapshot revisions with provider, observed time and content hash. [evidence: `vnalpha/company_context.py`, focused company-context contract test]
- [x] 2.3 Expose one shared company-context result for CLI/TUI/assistant. [evidence: `CurrentSymbolResearchResult.company_context`, `vnalpha/tools/current_symbol_research.py`, `vnalpha/cli_app/current_symbol.py`]
- [x] 2.4 Prove current share/industry fields do not leak into historical consumers. [evidence: focused company-context contract test]

### #330 — quote and intraday summary

- [ ] 2.5 Add typed quote/intraday clients and provider-drift fixtures.
- [ ] 2.6 Build one deterministic per-symbol/session summary.
- [ ] 2.7 Persist only bounded summary revisions, not unbounded tick history.
- [ ] 2.8 Distinguish valid empty, stale, unsupported and provider failure.

### #336 — foreign flow

- [ ] 2.9 Select one canonical dataset name and implement one verified Vietnamese provider path.
- [ ] 2.10 Add route, quality rules, typed client and idempotent daily persistence.
- [ ] 2.11 Build latest and bounded 5/20-session flow context.
- [ ] 2.12 Prove incremental tail sync and optional core behavior.

## 3. Publication-aware fundamentals

### #331 — `vnstock` contracts

- [ ] 3.1 Add the common publication/revision metadata envelope to all four statement contracts.
- [ ] 3.2 Normalize the bounded common fact set.
- [ ] 3.3 Verify at least one KBS or VCI path and explicit current-only/partial semantics.
- [ ] 3.4 Add quality tests for publication time, scope, unit, period and revisions.

### #332 — `vnalpha` facts and snapshots

- [ ] 3.5 Persist immutable financial fact revisions and supersession links.
- [ ] 3.6 Implement `fundamental_snapshot(symbol, as_of_date)` with no future availability.
- [ ] 3.7 Add bounded derived metrics with exact source lineage.
- [ ] 3.8 Link verified financial-report publication events to exactly matching statement revisions without changing values.
- [ ] 3.9 Prove ambiguous/unlinked facts remain historical-ineligible.
- [ ] 3.10 Add queue submit/join/reuse and historical no-enqueue tests.

## 4. Official disclosures and effective-dated facts

### #333 — official disclosures

- [ ] 4.1 Add canonical disclosure metadata contract and one approved bounded official-source adapter.
- [ ] 4.2 Normalize the allowlisted event types and preserve publication/effective dates separately.
- [ ] 4.3 Add optional statement-link metadata supplied by the official source.
- [ ] 4.4 Persist immutable occurrences, revisions and verified/quarantined events.
- [ ] 4.5 Prove unapproved sources and ambiguous events cannot emit verified facts.

### #334 — share count

- [ ] 4.6 Add `reference.share_count_fact` contract and route.
- [ ] 4.7 Persist current-only and historical-eligible revisions distinctly.
- [ ] 4.8 Implement `share_count_as_of()` with future-publication and ambiguity guards.
- [ ] 4.9 Prove current values are never substituted for missing historical facts.

### #335 — index membership

- [ ] 4.10 Add `reference.index_membership_revision` contract and route.
- [ ] 4.11 Deliver one fixture-backed VN30 revision sequence.
- [ ] 4.12 Implement `index_members_as_of()` with effective/availability and ambiguity rules.
- [ ] 4.13 Keep current membership and sector snapshots historical-ineligible unless verified.

## 5. Derived consumers

### #341 — official action reconciliation

- [ ] 5.1 Add a versioned mapping for supported official corporate-action events.
- [ ] 5.2 Reconcile exact matches, conflicts and revisions without deleting provider evidence.
- [ ] 5.3 Emit one affected range for accepted revisions.
- [ ] 5.4 Rebuild only affected adjustment and adjusted-series intervals.
- [ ] 5.5 Prove raw canonical OHLCV remains unchanged and downstream lineage updates.

### #342 — valuation context

- [ ] 5.6 Build optional P/E, earnings-yield, P/B and book-yield metrics from exact persisted inputs.
- [ ] 5.7 Add historical and sector-relative percentiles using point-in-time comparable evidence.
- [ ] 5.8 Fail closed per metric for missing, zero, negative or incompatible inputs.
- [ ] 5.9 Persist immutable valuation revisions and one shared typed result.
- [ ] 5.10 Prove valuation does not block or mutate existing price/ranking policy.

## 6. Program integration and validation — #327

- [ ] 6.1 Map every queued vertical to #338 goals/enrichments; no private job payloads.
- [ ] 6.2 Prove every optional dataset leaves existing core readiness unchanged.
- [ ] 6.3 Run contract, quality, point-in-time, no-lookahead, idempotency and queue tests.
- [ ] 6.4 Run full repository gates and OpenSpec validation on exact SHAs.
- [ ] 6.5 Synchronize only accepted implemented requirements into `openspec/specs`.
- [ ] 6.6 Close #327 only when every advertised dataset status is truthful and every completed consumer has validation evidence.
