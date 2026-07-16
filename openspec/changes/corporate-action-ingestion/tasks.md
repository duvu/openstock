## 1. vnstock provider contract

- [x] 1.1 Register `reference.corporate_actions` and its canonical columns.
- [x] 1.2 Add deterministic action taxonomy, dates, terms, provenance and hashes.
- [x] 1.3 Add bounded KBS/VCI provider adapters and truthful partial capabilities.
- [x] 1.4 Add the canonical HTTP service path and contract tests.

## 2. vnalpha canonical ingestion

- [x] 2.1 Add raw evidence, canonical revision, source-link, quarantine and affected-range tables.
- [x] 2.2 Implement raw-first validation and symbol lifecycle resolution.
- [x] 2.3 Implement idempotency, supersession and cross-provider conflict preservation.
- [x] 2.4 Add bounded client, provisioning, sync and status surfaces.

## 3. Documentation and validation

- [x] 3.1 Update current vnstock/vnalpha documentation in the implementation PR.
- [x] 3.2 Add focused fixtures for supported action types, empty, revision, conflict and quarantine cases.
- [ ] 3.3 Run repository consistency, focused tests, full CI and both package builds on the exact final SHA.
