## 1. Required spec and baseline

- [x] 1.1 Strictly validate the `consolidate-authoritative-test-suite` registry, proposal, design, tasks and six required capability specs.
- [x] 1.2 Record the base commit, clean tree, environment identity, collection count, sequential duration, slow tests and aggregate duplication.
- [x] 1.3 Add `make test-loop TEST=<nodeid>` with a hard 60-second, fail-fast bound.
- [x] 1.4 Remove sequential R0/R4/full and duplicate `openstock-verify --ci` execution from the canonical aggregate path.

## 2. Authoritative inventory and budget

- [x] 2.1 Inventory every current test and validation check as `KEEP`, `MERGE`, `REPLACE` or `DELETE` with retained-owner evidence.
- [x] 2.2 Create one concise authoritative manifest that maps every retained public/risk contract to one test node and domain.
- [x] 2.3 Make consistency reject a missing test node, duplicate contract identifier, unclassified new test, or authoritative count above 250.
- [x] 2.4 Consolidate the manifest to 180–220 authoritative tests, with explicit exceptions only for distinct approved risk contracts.
- [x] 2.5 Remove duplicate checker tests/scripts and policy prose after their real owner is retained.

## 3. Validation lanes and routing

- [x] 3.1 Classify docs/OpenSpec-only, component, packaging, shared-contract and infrastructure changes fail-closed.
- [x] 3.2 Keep consistency unconditional; let docs-only changes deliberately skip runtime lanes; fail Required on every conclusion other than `success` or `skipped`.
- [ ] 3.3 Route changed domains to their compact authoritative tests and demonstrate a PR wall-time target of five minutes or less.
- [x] 3.4 Restrict Debian acceptance to packaging, installer, dependency-layout, service-unit or release changes; ordinary `vnalpha/src/**` changes must not trigger it.

## 4. Fixture and consolidation implementation

- [x] 4.1 Add one migrated DuckDB template per worker and isolated copy-per-test reuse for compatible contracts.
- [x] 4.2 Prove the isolated copy fixture prevents mutation contamination and migrate compatible current-schema contracts.
- [ ] 4.3 Keep fresh migration, idempotency, upgrade, rollback, crash, reopen, locking and multiprocessing contracts on dedicated inputs.
- [ ] 4.4 Replace repeated table counts/lists with one canonical schema owner and consolidate equivalent application/CLI/TUI/assistant cases to their public boundary.
- [x] 4.5 Record retained financial, PIT, lineage, recovery, security and package-risk owners for every deletion.

## 5. Final evidence and closure

- [ ] 5.1 Freeze one final SHA; run strict OpenSpec, the bounded local contract, compact affected-domain lane and the complete authoritative suite once.
- [ ] 5.2 Run Debian acceptance only if its routed inputs changed; record before/after count, durations, migration setup and duplicate-execution measurements on equivalent environments.
- [ ] 5.3 Obtain independent specification/code-quality review, push the branch, open a PR closing #348, observe required CI on the exact SHA and fix failures without weakening coverage.
- [ ] 5.4 Merge the approved PR, confirm #348 closed, archive the OpenSpec and validate the archived state on `main`.
