## 1. Feature completeness contract and migration

- [x] 1.1 Add failing evaluator tests for 19/20/60/100/120/252-bar histories, missing fields, stale data, and missing benchmark-relative strength. [evidence: `uv run pytest tests/test_feature_completeness.py -q` passed after the test first failed with the expected missing-module import at this branch state]
- [x] 1.2 Implement the typed, versioned profile evaluator with separate neutral and relative-strength outcomes. [evidence: `uv run pytest tests/test_feature_completeness.py -q` and Ruff checks passed]
- [x] 1.3 Add additive `feature_snapshot` evidence columns and an idempotent migration that marks old rows `LEGACY_UNKNOWN`. [evidence: focused migration and snapshot-store tests passed]
- [x] 1.4 Add warehouse migration and persistence tests proving legacy rows remain readable but cannot satisfy a profile. [evidence: `uv run pytest tests/test_feature_completeness.py tests/test_r0_gaps.py::test_migrations_mark_pre_profile_feature_rows_legacy_unknown -q` passed]

## 2. Feature construction evidence

- [x] 2.1 Add failing build tests that prove new snapshots persist profile, counts, missing fields, outcomes, and rule version. [evidence: the new migrated-schema build tests failed first with null completeness evidence]
- [x] 2.2 Evaluate and persist completeness evidence from the canonical feature-build path without changing benchmark selection or freshness semantics. [evidence: focused evaluator, builder, migration, and persistence tests passed]
- [x] 2.3 Verify benchmark-neutral completeness remains truthful when relative-strength data is absent. [evidence: `test_build_features_keeps_neutral_evidence_when_benchmark_missing` passed]

## 3. Capability-specific consumer enforcement

- [x] 3.1 Add failing scoring tests proving incomplete or legacy standard-profile snapshots cannot generate candidate scores. [evidence: scoring test failed first with legacy row scored, then passed]
- [x] 3.2 Enforce the declared scoring profile and typed exclusion evidence at the score boundary. [evidence: scoring, benchmark-relative-strength, and focused completeness tests passed]
- [x] 3.3 Add failing market-breadth and sector-strength tests for exact-date profile selection and missing relative strength. [evidence: legacy breadth and incomplete-RS sector tests failed first, then passed]
- [x] 3.4 Enforce benchmark-neutral minimum evidence for breadth and relative-strength evidence for sector strength without changing their methodology thresholds. [evidence: breadth, sector-strength, and market-regime regression suites passed]
- [x] 3.5 Add readiness tests proving profile evidence is surfaced as a typed, sanitized quality failure where feature readiness is required. [evidence: readiness evidence test failed first with `available=True`, then passed with `INCOMPLETE_FEATURE_PROFILE`]

## 4. Surface and regression validation

- [x] 4.1 Exercise the feature-build and score CLI paths against an offline warehouse fixture, including an incomplete input rejection. [evidence: isolated DuckDB fixture: `vnalpha build features --date 2024-01-10 --symbols FPT,BAD --benchmark VNINDEX` reported `built: 1, skipped: 1`; `vnalpha score` scored and saved FPT only; persisted FPT as `STANDARD_120` with both outcomes `COMPLETE`]
- [x] 4.2 Exercise affected TUI/assistant/readiness adapters or record an evidence-backed no-direct-surface determination. [evidence: source search confirms no TUI or assistant renderer directly reads `feature_snapshot`; assistant/TUI command text delegates feature construction to the shared provisioning/readiness path, and readiness evidence regressions cover that adapter]
- [x] 4.3 Run focused tests, `make verify-r0`, full `vnalpha` tests, lint/format, strict OpenSpec validation, and relevant packaging checks; record exact outcomes and follow-up issues for any deferred failures. [evidence: PR #133 final head `3705d7fceb6a35c103bd7e251075e8f8fc02a380`; `openstock-ci` run #15 (`29411768105`) passed repository consistency, hygiene, secret scan, Compose validation, Ruff, focused regressions, `make verify-r0`, the complete `vnalpha` suite, 347 targeted `vnstock` provider/canonical tests, and wheel/sdist builds; merged to `main` as `4fbae6ba8eb51e90baf92fc93f5ddb4ee6e93de0`]

## Closure

- Primary implementation issue: #83 — completed.
- Repository validation owner: #131 — completed by PR #133.
- Lifecycle reconciliation: #134.
- Accepted specification: `openspec/specs/feature-completeness-profiles/spec.md`.
- Archived on: 2026-07-15.
