## Context

OpenStock currently has more than three thousand `vnalpha` tests plus `vnstock`, repository, packaging and installed-host checks. The root aggregate runs standalone R0 and R4 collections immediately before or after the full `vnalpha` suite that already collects those files, and `openstock-verify --ci` is invoked through more than one aggregate path. Pull requests also run broad component jobs without a checked mapping from changed paths to the contracts they can affect.

Issue #348 defines a contract-level H+1 policy and requires a compact inventory of approximately 180–220 authoritative tests, with a hard cap of 250. The change must preserve high-risk financial, point-in-time, lineage, transaction, recovery, fail-closed, migration and package scenarios. Every before/after claim must identify the exact commit, machine/runtime identity, command, collection count and duration.

The repository already provides the authoritative boundaries: root Make targets, `.github/workflows`, `scripts/check-repo-consistency.py`, `vnalpha` pytest configuration and package acceptance scripts. The design extends those seams instead of creating a parallel validation system.

Stakeholders are developers running local validation, pull-request authors, reviewers relying on the Required merge gate, release operators and future contributors adding tests. The research-only product boundary is unchanged.

## Goals / Non-Goals

**Goals:**

- Make the minimum sufficient test set explicit at the public-contract level.
- Reduce the retained authoritative inventory to 180–220 tests and fail consistency above 250.
- Avoid executing the same pytest file more than once in an aggregate lane.
- Route pull requests to consistency, smoke, affected-domain, full-regression and package lanes using fail-closed path classification.
- Reuse expensive DuckDB migration setup without sharing mutable database state.
- Measure and materially reduce local and required-PR feedback while keeping truthful diagnostics.
- Permit controlled parallel execution only after repeated equivalence and isolation evidence.

**Non-Goals:**

- Weakening a contract to meet the inventory or time target.
- Removing standalone R0 or R4 developer commands.
- Replacing full nightly, release or manual regression and package acceptance.
- Treating skipped, cancelled or unknown jobs as success.
- Changing application behavior, warehouse production semantics or research boundaries.
- Hiding flakes with retries or broad `continue-on-error`.

## Decisions

### 1. A concise manifest is the canonical authoritative inventory

The replacement manifest will assign each retained public or approved risk contract to one test node and one domain, and will enforce the 250-test hard cap. The current file-level suite manifest is an interim routing inventory; it is not sufficient evidence for a contract-level budget because one suite entry can select thousands of nodes.

TOML is selected because Python 3.11 can parse it with `tomllib` in the repository consistency job without installing application dependencies. Directory naming or pytest markers alone were rejected: names drift, markers are easy to omit and neither supplies replacement evidence for consolidation.

`vnstock-contracts` and `packaging` remain separate domain lanes owned by their existing trees and shell acceptance commands; the root routing manifest names those lanes without forcing non-pytest files into the `vnalpha` inventory.

### 2. One runner resolves a lane to one deduplicated pytest collection

`scripts/run-test-suite.py` will parse the manifest, resolve one or more domains, deduplicate paths while preserving stable order and either print the plan or invoke pytest once. Standalone Make targets remain thin named selections. Aggregate targets select the full inventory once and must not call R0/R4 around it.

A manifest-aware checker will fail for a missing test node, duplicate contract identifier, unsupported risk exception, unclassified new test or a count above 250. Direct hand-maintained pytest lists were rejected because they reproduce the drift this change is intended to remove.

### 3. Change impact is a typed, fail-closed classification

`scripts/classify-test-impact.py` will parse normalized repository-relative paths and emit a JSON decision containing classifications and required lanes. Initial classifications are `docs_openspec_only`, `vnalpha`, `vnstock`, `packaging`, `shared_contract` and `test_or_workflow_infrastructure`.

Docs/OpenSpec-only changes select consistency/spec only. Component changes select fast smoke plus the owning domains. Shared contracts select all affected component domains. Test, fixture, migration, manifest, routing, Make or workflow changes select full regression and applicable package acceptance. Any unknown path produces a failing decision and can never become docs-only.

The script, rather than workflow-expression duplication, is the policy source. Workflow jobs consume its outputs and run independently so smoke and full/domain work can execute in parallel.

### 4. The Required gate distinguishes deliberate skip from missing evidence

Consistency always runs. Conditional runtime/package jobs report either `success` or GitHub's deliberate `skipped` conclusion. The always-evaluated Required job accepts only those two conclusions for jobs present in its fixed `needs` list and rejects `failure`, `cancelled`, `timed_out`, `action_required`, `neutral`, `startup_failure` or an unknown/missing conclusion.

Artifact uploads may remain best-effort because they are diagnostics, not validation. Test commands, routing and required conclusions never use `continue-on-error`.

### 5. H+1 consolidation is replacement-based

The inventory operation is per public contract or externally observable state transition, not per helper, literal input, adapter or branch. Each contract retains one representative normal case and one highest-value edge/failure case. Equivalent literal variants become parameters. CLI, TUI and assistant retain bounded adapter/parity tests while shared domain behavior stays at the application/domain boundary.

Additional cases require one approved risk category in the manifest: point-in-time/no-lookahead, corporate-action adjustment/invalidation, provider provenance conflict, transaction/crash/recovery, queue lease/idempotency/writer exclusion, security/fail-closed, migration upgrade/rollback, package state preservation, policy promotion/rejection/rollback or cross-version compatibility.

A test is removed only when the change records its retained contract owner and replacement H, +1 or exception. Phase-named or implementation-detail tests are migration candidates, not automatic deletions.

### 6. DuckDB reuse copies immutable migrated templates

A session fixture will create a migrated template warehouse once per worker. Tests requesting a normal migrated warehouse receive a filesystem copy at an isolated per-test path. Mutable connections are never shared. Tests for fresh migration, migration idempotency, supported upgrade and rollback use dedicated empty or versioned inputs and bypass the template.

Transaction rollback reuse is limited to tests whose contract does not include commit, crash, reopen, lock, multiprocessing or file lifecycle semantics. Module-scoped synthetic pipelines are permitted only when setup inputs are identical and each assertion consumes immutable outputs.

One canonical schema manifest replaces repeated hard-coded table counts/lists; dedicated schema/migration tests own the manifest contract.

### 7. Parallel pytest is an evidence-gated optional mode

`pytest-xdist` may be added only after the isolated fixture suite passes sequentially and with `-n auto --dist loadfile` repeatedly on the same commit. The standard sequential command remains the rollback switch, and nightly retains a sequential full run during observation. A parallel run is rejected if it changes collection, outcomes, persisted artifacts or reveals order/global-state dependence.

### 8. Measurement artifacts are durable completion evidence

`openspec/changes/consolidate-authoritative-test-suite/evidence/` will contain baseline and final reports with commit, dirty state, OS, CPU, memory, Python, DuckDB, pytest and dependency identity; collection count; sequential wall time; duration by file/domain; top 100 slow tests; repeated aggregate files; and measurable migration counts. CI evidence records job wall times and conclusions for the exact final commit.

The local fast-smoke target is accepted only at or below 60 seconds in the recorded environment. Required-PR improvement must be material and compared on equivalent runner/environment data; otherwise the remaining blocker is explicitly recorded and the task remains incomplete.

## Risks / Trade-offs

- **[Risk] Consolidation removes a unique correctness boundary** → Require contract/replacement evidence, preserve approved risk exceptions and review semantic expectations before deletion.
- **[Risk] Path routing skips a needed lane** → Fail closed on unknown and infrastructure paths, test positive and negative routing matrices, and keep consistency always running.
- **[Risk] Conditional jobs weaken branch protection** → Keep a fixed always-evaluated Required job and accept only success or deliberate skip.
- **[Risk] Template databases leak mutable state** → Copy per test/worker, never share connections and run contamination/order probes.
- **[Risk] xdist exposes global vendor quota, localhost or singleton leaks** → Reset owned global state, isolate provider endpoints and retain sequential nightly/rollback mode.
- **[Risk] Manifest maintenance becomes overhead** → Make unassigned or stale entries fail repository consistency with actionable remediation.
- **[Trade-off] Full regression still costs time** → Run it for nightly/release/manual and high-risk infrastructure changes; ordinary PRs gain faster, targeted feedback.

## Migration Plan

1. Strictly validate this OpenSpec and record baseline measurements on the exact base commit.
2. Add manifest schema, checker and runner with no test deletion; prove current files are assigned exactly once.
3. Remove sequential aggregate duplication while retaining standalone R0/R4 commands.
4. Add path classifier and conditional parallel CI jobs with fail-closed Required semantics.
5. Classify contracts and consolidate the highest-confidence duplicate groups in focused commits, recording replacement coverage and before/after counts.
6. Introduce isolated migrated-template fixtures and migrate compatible tests; retain dedicated migration/lifecycle cases.
7. Measure sequential results, then add/enable optional xdist only if repeated equivalence passes.
8. Run full regression, package/operational acceptance, strict OpenSpec and CI on the exact final commit; record final evidence.

Rollback is configuration-first: use the sequential full runner, disable conditional/parallel selection and restore the previous aggregate workflow while keeping the inventory evidence. Any collection mismatch, flake, contamination or correctness regression blocks parallelization and test deletion.

## Open Questions

No product decision remains open. Baseline measurement will determine the exact duplicate groups worth consolidating and whether controlled parallel execution meets the equivalence gate on this repository and runner.
