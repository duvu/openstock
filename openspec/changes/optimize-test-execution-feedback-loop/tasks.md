## 1. Spec and baseline gate

- [x] 1.1 Register issue #348 and strictly validate proposal, design, four capability specs and tasks.
- [x] 1.2 Record the exact base commit, clean-tree state, OS, CPU, memory, Python, DuckDB, pytest and dependency identity.
- [x] 1.3 Record `vnalpha` collection count and the full sequential wall time with JUnit output and top 100 tests at or above 0.20 seconds.
- [x] 1.4 Aggregate baseline runtime by file and initial domain without double-counting parameterized cases.
- [x] 1.5 Record every pytest file repeated by current aggregate Make/CI paths and every repeated `openstock-verify --ci` invocation.
- [ ] 1.6 Record measurable full migration invocation counts and docs/OpenSpec-only PR lane behavior/runtime.

## 2. Canonical ownership and H+1 policy

- [x] 2.1 Add the TOML suite manifest schema for domain, contract, H, +1 and approved risk-exception ownership.
- [x] 2.2 Add a consistency checker that rejects missing paths, unassigned or multiply assigned test files, unsupported roles/categories and contracts without H+1.
- [x] 2.3 Add RED/GREEN checker tests for valid inventory, unassigned files, duplicate ownership, missing H/+1 and invalid exception categories.
- [x] 2.4 Inventory every `vnalpha/tests/test_*.py` file under exactly one `vnalpha-data`, `vnalpha-research`, `vnalpha-application`, `shared-smoke` or `migration` owner.
- [ ] 2.5 Record canonical contract ownership for `vnstock-contracts` and packaging validation lanes.
- [x] 2.6 Integrate suite ownership validation into repository consistency and the every-PR consistency lane.

## 3. Deduplicated execution lanes

- [x] 3.1 Add a typed suite runner that resolves manifest selections, preserves stable order, rejects unknown suites and invokes pytest once with deduplicated paths.
- [x] 3.2 Add RED/GREEN runner tests for domain selection, overlapping selections, deterministic plans, unknown suites and pytest exit propagation.
- [x] 3.3 Add Make targets for consistency/spec, fast smoke, each affected domain, full regression and the canonical aggregate path.
- [x] 3.4 Keep `verify-r0` and `verify-r4` standalone while removing their sequential execution around the full suite in aggregate targets.
- [x] 3.5 Ensure each aggregate path invokes `openstock-verify --ci` at most once and preserves logs/failure diagnostics.
- [x] 3.6 Prove the canonical aggregate plan contains no repeated pytest file and retains all currently collected full-suite files.

## 4. Fail-closed change-impact routing

- [ ] 4.1 Add a typed path classifier for docs/OpenSpec-only, vnalpha, vnstock, packaging, shared-contract and test/workflow-infrastructure changes.
- [ ] 4.2 Add RED/GREEN classifier tests for every class, mixed changes, unknown paths, normalized paths and infrastructure/full-regression escalation.
- [ ] 4.3 Emit deterministic JSON and GitHub Actions outputs listing required smoke, domain, full and package lanes.
- [ ] 4.4 Update `openstock-ci.yml` so consistency always runs and smoke/domain/full jobs consume classifier outputs independently.
- [ ] 4.5 Update package workflow routing so packaging/release-relevant changes run full Debian acceptance and docs-only changes do not.
- [ ] 4.6 Make the Required merge gate accept only `success` or deliberate `skipped` conclusions and fail every other/missing conclusion.
- [ ] 4.7 Add workflow/consistency regressions proving docs-only safe skips, unknown-path failure, parallel job eligibility and fail-closed Required conclusions.

## 5. H+1 consolidation

- [x] 5.1 Rank current duplicate/superseded, phase-named and implementation-detail test groups using baseline duration and contract ownership.
- [ ] 5.2 Consolidate repeated schema table counts/lists into one canonical schema manifest while retaining fresh migration, idempotency, upgrade and rollback contracts.
- [ ] 5.3 Consolidate equivalent repeated happy paths with parameterization and record retained H/+1 replacement coverage.
- [ ] 5.4 Consolidate repeated CLI/TUI/assistant domain scenarios to bounded adapter/parity cases while retaining domain behavior at the application boundary.
- [x] 5.5 Remove only duplicate/superseded or implementation-detail tests with manifest-linked replacement evidence.
- [ ] 5.6 Prove no financial correctness, PIT/no-lookahead, lineage, transaction, recovery, security/fail-closed, migration or package boundary lost its owner.

## 6. DuckDB fixture reuse

- [ ] 6.1 Add a session/worker migrated-template fixture and isolated per-test copy fixture with real mutation-contamination tests.
- [ ] 6.2 Migrate compatible tests from repeated full migration setup to the isolated template fixture.
- [ ] 6.3 Keep commit, crash, reopen, locking, multiprocessing, fresh migration, upgrade and rollback tests on dedicated file-backed inputs.
- [ ] 6.4 Reuse module-scoped synthetic pipeline outputs only where inputs and outputs are immutable and equivalent.
- [ ] 6.5 Measure and record final full-migration invocation count and fixture setup time against baseline.

## 7. Controlled parallelization

- [ ] 7.1 Add `pytest-xdist` and a documented `-n auto --dist loadfile` command only after fixture isolation tests pass sequentially.
- [ ] 7.2 Run the full collection sequentially and in parallel repeatedly on the same commit, comparing collection, outcomes and artifacts.
- [ ] 7.3 Fix any global quota, localhost, singleton, file-path or ordering leak exposed by parallel execution without adding retries.
- [ ] 7.4 Keep a simple sequential rollback target and a sequential nightly full lane during observation.
- [ ] 7.5 Enable parallel PR execution only if repeated equivalence is proven; otherwise record the blocker and leave parallel mode disabled.

## 8. Validation, evidence and closure

- [ ] 8.1 Run the fast-smoke command and record a local wall time at or below 60 seconds, or leave the criterion incomplete with exact blocker evidence.
- [ ] 8.2 Run affected-domain, full sequential regression, selected parallel regression if enabled, Ruff/format and repository consistency on the exact final commit.
- [ ] 8.3 Run R0 and R4 standalone commands and prove their aggregate files execute only once in the canonical full/aggregate plan.
- [ ] 8.4 Run `vnstock` contract/package validation and full Debian fresh-install, upgrade, rollback and state-preservation acceptance when routed.
- [ ] 8.5 Record before/after counts, durations, duplicate files, migration counts and environment identity in durable evidence artifacts.
- [ ] 8.6 Exercise the local runner and classifier through their real CLI surfaces, including invalid suite and unknown-path failures.
- [ ] 8.7 Strictly validate the OpenSpec, record exact final SHA evidence for every checked task and pass the completion verifier.
- [ ] 8.8 Obtain independent spec and code-quality review, disposition every finding and rerun affected gates on the reviewed SHA.
- [ ] 8.9 Push the branch, open a PR closing #348, observe required CI on the exact SHA and fix every failure without weakening coverage.
- [ ] 8.10 Merge the approved PR, confirm issue #348 closed, archive the completed OpenSpec, synchronize accepted specs and rerun completion validation on `main`.
