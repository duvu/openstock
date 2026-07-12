# Tasks: OpenStock four-phase hardening

## How to use this checklist

Execute tasks in numeric order unless a task explicitly lists independent dependencies. Read `execution.md` before changing code.

Task annotations:

```text
[depends: IDs]  prerequisites that must be complete
[files: paths]  expected primary file areas
[evidence: ...] minimum proof required before checking the task
```

All tasks are unchecked intentionally. Do not bulk-check tasks from a PR description.

# 0. Governance and baseline

- [x] **0.1 Record baseline commit and repository state.** Capture current `main` SHA, tracked denied paths, gitlinks, open hardening-related PRs, and current CI status in `validation.md`. [evidence: `git rev-parse HEAD`, `git ls-files`, `git ls-files --stage`, GitHub check links]
- [ ] **0.2 Freeze unrelated agentic/research feature work during P0 remediation.** Document accepted exceptions and owners. [depends: 0.1] [evidence: project note/PR description]
- [ ] **0.3 Create implementation branches/PRs using the phase split in `execution.md`.** [depends: 0.1] [evidence: branch and draft PR links]
- [x] **0.4 Add a validation evidence row format to `validation.md` and use it for every command.** [evidence: committed validation template]
- [x] **0.5 Confirm the research-only product boundary remains unchanged.** No broker/account/order/allocation/margin/execution capability may be added. [evidence: policy regression test]
- [ ] **0.6 Confirm backward-compatibility surfaces that must remain:** `vnalpha.cli:app`, existing safe tool names, workspace JSON migration, and `AssistantApp.ask` wrapper. [evidence: compatibility tests]

# Phase 1 — Repository and data safety

## 1A. Repository cleanup and recurrence prevention

- [x] **1.1 Add denied runtime/generated paths to `.gitignore`.** Include `.vnalpha/`, `vnalpha/.vnalpha/`, `.worktrees/`, `*.egg-info/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, and `*.pyc`. [files: `.gitignore`] [evidence: ignore tests or `git check-ignore -v`]
- [x] **1.2 Inventory all currently tracked denied paths and gitlinks.** [depends: 1.1] [evidence: saved `git ls-files` and `git ls-files --stage` output]
- [x] **1.3 Remove root `.vnalpha/` runtime files from Git index without silently deleting the operator's local copy.** [depends: 1.2] [evidence: diff and hygiene check]
- [x] **1.4 Remove `vnalpha/.vnalpha/` runtime files from Git index.** [depends: 1.2] [evidence: diff and hygiene check]
- [x] **1.5 Remove `.worktrees/` gitlinks from Git index.** [depends: 1.2] [evidence: no unapproved mode `160000` entries]
- [x] **1.6 Remove tracked egg-info and Python/test/lint cache artifacts.** [depends: 1.2] [evidence: no denied tracked paths]
- [x] **1.7 Add `packaging/scripts/openstock-repo-hygiene` or equivalent deterministic verifier.** [files: `packaging/scripts/`, tests] [evidence: verifier passes clean tree and fails seeded denied path]
- [x] **1.8 Make hygiene verifier reject unapproved gitlinks.** [depends: 1.7] [evidence: unit/integration test with mode 160000 fixture]
- [x] **1.9 Add a documented approved-submodule allowlist mechanism, even if initially empty.** [depends: 1.8] [evidence: config/schema test]
- [x] **1.10 Add root Make target `repo-hygiene`.** [depends: 1.7] [files: `Makefile`] [evidence: `make repo-hygiene` exit 0]
- [x] **1.11 Add a secret/sensitive-content scanner for current tracked files.** Use an approved tool or repository-owned scanner. [files: CI/scripts] [evidence: seeded secret test fails]
- [x] **1.12 Scan current Git history and record whether history rewriting is required.** Do not rewrite automatically. [depends: 1.11] [evidence: scan command/output and decision in validation]
- [x] **1.13 Add a repository-hygiene regression test to CI preparation.** [depends: 1.10, 1.11] [evidence: workflow step/test]

## 1B. Deterministic workspace root and migration

- [x] **1.14 Select and document the canonical default workspace root.** Recommended: platform user-state directory. [files: workspace docs/config]
- [x] **1.15 Implement deterministic root resolution precedence:** explicit argument, env override, platform default. [depends: 1.14] [files: `workspace_context/storage.py` or new config module] [evidence: unit tests]
- [x] **1.16 Prove root resolution is identical from repository root, `vnalpha/`, and an unrelated CWD.** [depends: 1.15] [evidence: parametrized test]
- [x] **1.17 Add legacy root detection for project-local `.vnalpha/workspaces`.** [depends: 1.15] [evidence: migration discovery test]
- [x] **1.18 Add explicit legacy workspace migration command/service.** It must not silently merge multiple roots. [depends: 1.17] [evidence: migration integration test]
- [x] **1.19 Preserve source workspace as backup/quarantine during migration.** [depends: 1.18] [evidence: backup existence/checksum test]
- [x] **1.20 Add operator documentation for workspace root and migration.** [depends: 1.18] [evidence: docs link]

## 1C. Transactional workspace locking

- [x] **1.21 Add `workspace_context/locking.py` with atomic lock acquisition.** Prefer `flock`; support exclusive-create fallback. [files: workspace package] [evidence: unit tests]
- [x] **1.22 Store owner token, PID, host, and created timestamp in lock metadata.** [depends: 1.21] [evidence: metadata test]
- [x] **1.23 Verify owner token before release.** An old owner must not delete a newer lock. [depends: 1.22] [evidence: stale-owner test]
- [x] **1.24 Implement bounded wait/timeout and structured lock contention error.** [depends: 1.21] [evidence: timeout test]
- [x] **1.25 Implement safe stale-lock detection and replacement.** [depends: 1.22] [evidence: stale-lock concurrency test]
- [x] **1.26 Add `workspace_transaction()` context manager covering load, mutate, save, event append, and release.** [depends: 1.21] [evidence: transaction test]
- [x] **1.27 Add `state_version` or equivalent optimistic version field to workspace schema.** [depends: 1.26] [evidence: migration/serialization tests]
- [x] **1.28 Migrate `record_input()` to transaction boundary.** [depends: 1.26] [evidence: no-lost-input test]
- [x] **1.29 Migrate `record_artifact()` to transaction boundary.** [depends: 1.26] [evidence: no-lost-artifact test]
- [x] **1.30 Migrate warning/error mutations to transaction boundary.** [depends: 1.26] [evidence: concurrency test]
- [x] **1.31 Migrate TODO/task mutations to transaction boundary.** [depends: 1.26] [evidence: concurrent task update test]
- [x] **1.32 Migrate workspace-scoped model override writes to transaction/atomic workspace path.** [depends: 1.26] [evidence: override persistence test]
- [x] **1.33 Add multi-process lost-update test with at least two concurrent writers.** [depends: 1.28, 1.29, 1.30, 1.31] [evidence: repeated test passes]

## 1D. Workspace lifecycle state machine

- [x] **1.34 Add explicit workspace schema version and canonical status enum/constants.** [files: models/migrations] [evidence: serialization tests]
- [x] **1.35 Split generic persistence from latest activation.** Saving state must not update latest implicitly. [depends: 1.34] [files: persistence/lifecycle] [evidence: unit test]
- [x] **1.36 Make `create_workspace()` create ACTIVE state and update latest explicitly.** [depends: 1.35] [evidence: lifecycle test]
- [x] **1.37 Make `archive_workspace()` transition ACTIVE→ARCHIVED without setting latest to archived ID.** [depends: 1.35] [evidence: archive/latest regression test]
- [x] **1.38 Define and implement archived resume behavior:** explicit reactivation or explicit refusal. [depends: 1.37] [evidence: behavior test and docs]
- [x] **1.39 Make `get_or_create_latest_workspace()` reject/repair missing, archived, or corrupt latest pointers.** [depends: 1.37] [evidence: pointer recovery tests]
- [x] **1.40 Make `get_status()` read-only: no latest update, no resume event.** [depends: 1.35] [evidence: event/pointer non-mutation test]
- [x] **1.41 Make `new_workspace()` compact/archive current active state and then activate exactly one new state.** [depends: 1.37] [evidence: lifecycle E2E]
- [x] **1.42 Add lifecycle invariant checker:** zero or one active latest workspace; latest must reference active valid state. [depends: 1.39] [evidence: invariant tests]
- [x] **1.43 Add schema migration for existing archived/latest-invalid states.** [depends: 1.34, 1.39] [evidence: legacy fixture tests]

## 1E. Bounded retention and real compaction

- [x] **1.44 Add configurable limits for inputs, warnings, errors, artifacts, done tasks, and active events.** [files: workspace config] [evidence: config tests]
- [x] **1.45 Enforce bounded recent inputs during mutation.** Archive or rotate older entries rather than silently dropping without reference. [depends: 1.44, 1.26] [evidence: retention test]
- [x] **1.46 Enforce bounded warnings and errors.** [depends: 1.44, 1.26] [evidence: retention test]
- [x] **1.47 Enforce bounded active artifacts and completed tasks while preserving pinned/user-authored items.** [depends: 1.44, 1.26] [evidence: retention test]
- [x] **1.48 Add event rotation/archive format with checksums.** [depends: 1.44] [evidence: rotation test]
- [x] **1.49 Change compaction to archive old entries and reduce active workspace state.** [depends: 1.45, 1.46, 1.47, 1.48] [files: compaction] [evidence: before/after count test]
- [x] **1.50 Return compaction manifest with before, retained, archived counts and paths.** [depends: 1.49] [evidence: result contract test]
- [x] **1.51 Preserve pinned artifacts, open tasks, user notes, assumptions, and source refs during compaction.** [depends: 1.49] [evidence: preservation test]
- [x] **1.52 Add idempotency test: repeated compaction without new data does not keep creating duplicate archives.** [depends: 1.49] [evidence: idempotency test]

## 1F. Redaction and export safety

- [x] **1.53 Add canonical workspace redaction service returning text, status, and matched categories.** [files: `workspace_context/redaction.py`] [evidence: unit tests]
- [x] **1.54 Apply redaction to input content/summary.** [depends: 1.53] [evidence: tests]
- [x] **1.55 Apply redaction to tasks and TODO details.** [depends: 1.53] [evidence: tests]
- [x] **1.56 Apply redaction to warnings, errors, and assumptions.** [depends: 1.53] [evidence: tests]
- [x] **1.57 Apply redaction to artifact summaries and workspace audit metadata.** [depends: 1.53] [evidence: tests]
- [x] **1.58 Ensure `context.md` and `compact.md` contain redacted projections only.** [depends: 1.53] [evidence: golden text test]
- [x] **1.59 Replace raw workspace export with a versioned redacted projection.** [depends: 1.53] [files: export/export_projection] [evidence: export tests]
- [x] **1.60 Remove absolute `source_path` from export manifest.** [depends: 1.59] [evidence: manifest test]
- [x] **1.61 Exclude raw history/events by default; add explicit bounded `--include-history` option if retained.** [depends: 1.59] [evidence: command/export tests]
- [x] **1.62 Export only approved pinned artifacts with path traversal/symlink protections.** [depends: 1.59] [evidence: security tests]
- [x] **1.63 Add end-to-end redaction test from task/error input through compact and export bundle.** [depends: 1.55, 1.56, 1.58, 1.59] [evidence: E2E]

## Phase 1 gate

- [x] **1.G1 Run repository hygiene and secret scans.** [depends: 1.1–1.13] [evidence: command rows]
- [x] **1.G2 Run all workspace root, locking, concurrency, lifecycle, retention, redaction, and export tests.** [depends: 1.14–1.63] [evidence: test command rows]
- [x] **1.G3 Confirm no denied tracked paths or unapproved gitlinks remain.** [depends: 1.G1] [evidence: `git ls-files`, `git ls-files --stage`]
- [x] **1.G4 Confirm latest pointer/lifecycle invariants on migrated legacy fixtures.** [depends: 1.43] [evidence: migration E2E]
- [x] **1.G5 Record Phase 1 PASS in `validation.md`.** [depends: 1.G1–1.G4]

# Phase 2 — Context trust and assistant lifecycle

## 2A. Structured context trust boundary

- [x] **2.1 Add `AssistantRequest` model separating current prompt, workspace context, chat context, and date.** [depends: 1.G5] [files: assistant models] [evidence: serialization/unit tests]
- [x] **2.2 Add bounded context message builder that marks historical context untrusted and potentially stale.** [depends: 2.1] [evidence: message snapshot tests]
- [x] **2.3 Remove direct string concatenation of context and current prompt from the primary path.** [depends: 2.2] [evidence: architecture/source test]
- [x] **2.4 Run deterministic safety policy on current user prompt only.** [depends: 2.1] [evidence: malicious-context test]
- [x] **2.5 Run intent classification on current user prompt only.** [depends: 2.1] [evidence: context-injection classification test]
- [x] **2.6 Allow synthesizer to consume bounded context as a separate lower-trust field/message.** [depends: 2.2] [evidence: prompt contract test]
- [x] **2.7 Add test proving instructions embedded in task/compact context cannot select a tool or alter intent.** [depends: 2.4, 2.5]
- [x] **2.8 Add test proving fresh tool output overrides stale workspace summary.** [depends: 2.6]

## 2B. Prompt persistence policy

- [x] **2.9 Add prompt persistence projection with raw flag, summary, hash, chars, and context refs.** [depends: 2.1] [files: assistant repo/schema] [evidence: unit tests]
- [x] **2.10 Add backward-compatible warehouse migration for prompt metadata fields.** [depends: 2.9] [evidence: migration tests]
- [x] **2.11 Enforce `store_raw=false`: no full raw/prefixed prompt stored.** [depends: 2.9] [evidence: persistence test]
- [x] **2.12 Enforce `store_raw=true`: store only configured/redacted current request, not duplicated workspace/chat bodies.** [depends: 2.9] [evidence: persistence test]
- [x] **2.13 Store workspace/chat context references or hashes, not full duplicated context.** [depends: 2.9] [evidence: schema test]
- [x] **2.14 Add migration/read compatibility for historical assistant-session rows.** [depends: 2.10] [evidence: legacy-row test]

## 2C. Prepared-turn lifecycle

- [x] **2.15 Add `PreparedAssistantTurn` model with IDs, canonical plan JSON/hash, policy result, and creation time.** [depends: 2.1] [files: assistant models] [evidence: model tests]
- [x] **2.16 Add canonical stable plan serialization and SHA-256 hash function.** [depends: 2.15] [evidence: deterministic hash test]
- [x] **2.17 Add `AssistantApp.prepare()` performing safety, classification, intent policy, normalization, and plan build exactly once.** [depends: 2.15] [evidence: call-count tests]
- [x] **2.18 Persist prepared turn/plan identity for preview/approval.** [depends: 2.17] [evidence: repository tests]
- [x] **2.19 Add `AssistantApp.execute_prepared()` executing exact prepared plan without classifier/planner calls.** [depends: 2.17] [evidence: mock call-count and plan identity tests]
- [x] **2.20 Validate prepared-turn session ID and plan hash before execution.** [depends: 2.19] [evidence: mismatch refusal test]
- [x] **2.21 Keep `AssistantApp.ask()` as compatibility wrapper over prepare/execute.** [depends: 2.17, 2.19] [evidence: existing API tests]
- [x] **2.22 Update PLAN_ONLY mode to prepare once and render exact plan.** [depends: 2.17] [evidence: controller test]
- [x] **2.23 Update PLAN_THEN_APPROVE mode to store exact prepared turn.** [depends: 2.18] [evidence: controller test]
- [x] **2.24 Update approval flow to execute exact prepared turn, not rebuild from question.** [depends: 2.19, 2.23] [evidence: approved plan identity test]
- [x] **2.25 Update AUTO_EXECUTE_SAFE_TOOLS mode to prepare once and execute same prepared turn.** [depends: 2.17, 2.19] [evidence: classifier/planner called once]
- [x] **2.26 Add cancellation cleanup for prepared-turn state.** [depends: 2.23] [evidence: cancel test]
- [x] **2.27 Add observability for PREPARED, EXECUTED, CANCELLED, HASH_MISMATCH.** [depends: 2.17–2.26] [evidence: audit tests]

## 2D. TUI/workspace resilience

- [x] **2.28 Reorder TUI routing so busy rejection occurs before accepted-input persistence.** [depends: 1.G5] [files: TUI router] [evidence: busy input test]
- [x] **2.29 Add explicit rejected/not-executed event if busy submissions are retained for UX.** [depends: 2.28] [evidence: event test]
- [x] **2.30 Wrap workspace recording hooks as best-effort non-blocking operations.** [depends: 1.G5] [evidence: injected failure test]
- [x] **2.31 Ensure workspace hook failure cannot prevent command/chat execution.** [depends: 2.30] [evidence: integration test]
- [x] **2.32 Add workspace schema validation at startup.** [depends: 1.34] [evidence: invalid fixture tests]
- [x] **2.33 Add quarantine/recovery service for malformed workspace files.** [depends: 2.32] [files: recovery] [evidence: quarantine test]
- [x] **2.34 Start temporary/new safe workspace when canonical workspace cannot load.** [depends: 2.33] [evidence: headless TUI mount test]
- [x] **2.35 Render warning and `/context repair` guidance without blocking TUI.** [depends: 2.34] [evidence: output/status test]
- [x] **2.36 Add `/context repair` dry-run and apply behavior or explicitly defer with approved record.** [depends: 2.33] [evidence: command tests or defer record]

## Phase 2 gate

- [x] **2.G1 Run context trust/injection tests.** [depends: 2.1–2.8]
- [x] **2.G2 Run prompt persistence/store_raw tests.** [depends: 2.9–2.14]
- [x] **2.G3 Run prepared-turn call-count, hash, approval, cancellation, and compatibility tests.** [depends: 2.15–2.27]
- [x] **2.G4 Run headless TUI busy/workspace failure/recovery tests.** [depends: 2.28–2.36]
- [x] **2.G5 Record Phase 2 PASS in `validation.md`.** [depends: 2.G1–2.G4]

# Phase 3 — Runtime correctness

## 3A. Data-availability lock and input correctness

- [x] **3.1 Replace data-ensure check-then-write lock with atomic exclusive acquisition.** [depends: 2.G5] [files: data_availability/lock.py] [evidence: unit tests]
- [x] **3.2 Add owner token metadata and owner-safe release for data lock.** [depends: 3.1] [evidence: stale-owner test]
- [x] **3.3 Add safe stale-lock replacement under process contention.** [depends: 3.2] [evidence: multi-process test]
- [x] **3.4 Preserve `finally` release semantics and add exception-path test.** [depends: 3.1] [evidence: test]
- [x] **3.5 Split optional date resolution from explicit date validation.** [files: normalizers/data service] [evidence: unit tests]
- [x] **3.6 Make malformed explicit date raise validation error before any sync/build/score action.** [depends: 3.5] [evidence: fake-action zero-call test]
- [x] **3.7 Update user-facing command/assistant error text for invalid dates.** [depends: 3.6] [evidence: command tests]

## 3B. Cache eligibility and lineage

- [x] **3.8 Add `CacheEligibility` model and policy evaluator.** [depends: 2.G5] [files: data_availability] [evidence: unit tests]
- [x] **3.9 Require fresh candidate score for cache hit.** [depends: 3.8] [evidence: stale-score test]
- [x] **3.10 Require feature snapshot presence.** [depends: 3.8] [evidence: orphan-score test]
- [x] **3.11 Require sufficient canonical history.** [depends: 3.8] [evidence: insufficient-bars test]
- [x] **3.12 Require sufficient benchmark history when policy requires relative strength.** [depends: 3.8] [evidence: missing-benchmark test]
- [x] **3.13 Reject failed/unacceptable quality status.** [depends: 3.8] [evidence: quality test]
- [x] **3.14 Enforce configured lineage completeness.** [depends: 3.8] [evidence: missing-lineage test]
- [x] **3.15 Include cache rejection reasons in result and DATA_ENSURE_CACHE_REJECTED event.** [depends: 3.9–3.14] [evidence: observability test]
- [x] **3.16 Preserve fast cache hit when all conditions pass.** [depends: 3.9–3.14] [evidence: no-action test]

## 3C. Artifact references and research correctness

- [x] **3.17 Add verified artifact reference builder/helper.** [depends: 2.G5] [files: research tools/common] [evidence: unit tests]
- [x] **3.18 Change shortlist sector refs to emit only when sector snapshot query returned data.** [depends: 3.17] [evidence: no-sector test]
- [x] **3.19 Add `sector_strength_snapshot` to missing data/caveats when unavailable and component is omitted/defaulted.** [depends: 3.18] [evidence: payload test]
- [x] **3.20 Audit other research tools for unconditional artifact refs and correct them.** [depends: 3.17] [evidence: matrix test]
- [x] **3.21 Add artifact-ref integrity test from tool output through research-answer audit.** [depends: 3.17–3.20]

## 3D. Compaction, commands, UI events, and model scope

- [x] **3.22 Confirm real compaction behavior from Phase 1 is used by `/context compact`.** [depends: 1.49, 2.G5] [evidence: command E2E]
- [x] **3.23 Resolve `/new` namespace:** `/new` workspace alias, `/chat new` chat session. [files: parser/chat controller/help] [evidence: routing tests]
- [x] **3.24 Remove/deprecate ambiguous chat-local `/new` and add migration/help text.** [depends: 3.23] [evidence: docs/tests]
- [x] **3.25 Track previous TODO visibility and emit events only on transitions.** [files: TUI app] [evidence: resize test]
- [x] **3.26 Scope session model override by session ID or ContextVar.** [files: model routing override store] [evidence: two-session isolation test]
- [x] **3.27 Clean session override state when session ends.** [depends: 3.26] [evidence: lifecycle test]
- [x] **3.28 Update `/model status` to report effective scope/session identity safely.** [depends: 3.26] [evidence: command test]

## 3E. Source-reference semantics

- [x] **3.29 Stop auto-filling missing model-generated `grounded_source_refs` before validation.** [depends: 2.G5] [files: synthesizer] [evidence: missing-ref fallback test]
- [x] **3.30 Permit deterministic fallback to populate bounded source refs.** [depends: 3.29] [evidence: fallback test]
- [x] **3.31 Add optional `claim_source_refs` answer metadata contract.** [depends: 3.29] [evidence: parser/model tests]
- [x] **3.32 Add at least one runtime-replay case requiring claim-level source mapping.** [depends: 3.31, Phase 4 runtime runner]

## Phase 3 gate

- [x] **3.G1 Run data lock/date/cache eligibility focused tests.** [depends: 3.1–3.16]
- [x] **3.G2 Run research artifact-reference and grounded-source tests.** [depends: 3.17–3.21, 3.29–3.31]
- [x] **3.G3 Run context compact, command namespace, TODO event, and model isolation tests.** [depends: 3.22–3.28]
- [x] **3.G4 Run relevant existing regression suites for data availability, assistant, TUI, model routing, and workspace.** [depends: 3.G1–3.G3]
- [x] **3.G5 Record Phase 3 PASS in `validation.md`.** [depends: 3.G1–3.G4]

# Phase 4 — CI, evaluation, and release governance

## 4A. Lint and root operator commands

- [x] **4.1 Fix all existing Ruff check and format failures on the implementation base.** [depends: 3.G5] [evidence: `make lint-vnalpha`]
- [x] **4.2 Add root Make target `eval-research-answers`.** [files: root Makefile] [evidence: command]
- [x] **4.3 Add root Make target `eval-research-runtime`.** [evidence: command]
- [x] **4.4 Add root Make target `verify-hardening` running phase gates in documented order.** [depends: 4.2, 4.3, 1.10] [evidence: target dry run/full run]

## 4B. Package golden corpus

- [x] **4.5 Move or mirror golden fixtures into installable package resources.** [files: `vnalpha/src/vnalpha/evals/goldens/` or package-data config]
- [x] **4.6 Load default corpus using `importlib.resources`, not repository-relative parents.** [depends: 4.5] [evidence: unit tests]
- [x] **4.7 Declare package-data for wheel/sdist.** [depends: 4.5] [evidence: built artifact inspection]
- [x] **4.8 Ensure Debian packaging includes or correctly installs the corpus.** [depends: 4.5] [evidence: package verification]
- [x] **4.9 Add isolated installed-wheel eval test.** [depends: 4.6, 4.7] [evidence: CI command]
- [x] **4.10 Add installed-deb or packaging fixture eval check where feasible.** [depends: 4.8] [evidence: packaging test or approved defer]

## 4C. Runtime-replay evaluation

- [x] **4.11 Define typed runtime-replay case schema.** Fields include request, expected intent, seeded artifacts/tool outputs, fake LLM responses, expected plan, policy, groundedness, audit. [depends: 3.G5] [files: eval contracts/models] [evidence: schema tests]
- [x] **4.12 Add strict loader with unknown-field rejection and safe logical artifact refs.** [depends: 4.11] [evidence: loader tests]
- [x] **4.13 Add deterministic fake classifier/gateway adapter that uses production response parsers.** [depends: 4.11] [evidence: adapter tests]
- [x] **4.14 Add seeded in-memory warehouse/tool registry adapter using production tool interfaces.** [depends: 4.11] [evidence: adapter tests]
- [x] **4.15 Add runtime runner through `AssistantApp.prepare()` and `execute_prepared()`.** [depends: 2.17, 2.19, 4.13, 4.14] [evidence: E2E]
- [x] **4.16 Assert intent, exact plan tools/arguments, tool traces, groundedness, policy, fallback, and audit outcome.** [depends: 4.15] [evidence: check tests]
- [x] **4.17 Prohibit network access in runtime-replay mode.** [depends: 4.15] [evidence: network-block test]
- [x] **4.18 Add runtime-replay seed cases for all research intents.** [depends: 4.15] [evidence: corpus count/report]
- [x] **4.19 Add negative cases:** prompt injection in context, missing refs, fabricated number, missing sector artifact, invalid date, unsafe scenario wording. [depends: 4.15] [evidence: expected failure/rewrite reports]
- [x] **4.20 Add claim-source mapping case.** [depends: 3.31, 4.15]
- [x] **4.21 Add CLI `vnalpha eval research-runtime --ci`.** [depends: 4.15] [evidence: CLI tests]
- [x] **4.22 Add stable human-readable and machine-readable reports.** [depends: 4.15] [evidence: snapshot/schema tests]

## 4D. CI and diagnostics

- [x] **4.23 Add repository hygiene step as first CI gate.** [depends: 1.10]
- [x] **4.24 Add secret scan step.** [depends: 1.11]
- [x] **4.25 Keep focused hardening tests and upload diagnostics on failure.** [depends: Phase 1–3 focused suites]
- [x] **4.26 Require Ruff check and format check before full suite.** [depends: 4.1]
- [ ] **4.27 Run full `make test-vnalpha`.** [evidence: workflow]
- [x] **4.28 Run `make verify-r4`.** [evidence: workflow]
- [x] **4.29 Run `packaging/scripts/openstock-verify --ci`.** [evidence: workflow]
- [x] **4.30 Run fixture-contract eval.** [depends: 4.2]
- [x] **4.31 Run runtime-replay eval.** [depends: 4.3, 4.21]
- [x] **4.32 Run installed-package eval.** [depends: 4.9]
- [x] **4.33 Upload concise logs for each failed gate.** [depends: 4.23–4.32]
- [x] **4.34 Add concurrency control that cancels obsolete PR runs without canceling main validation.** [evidence: workflow review/test]

## 4E. OpenSpec completion governance

- [x] **4.35 Add `scripts/check-openspec-completion.py`.** [files: scripts/tests] [evidence: unit tests]
- [x] **4.36 Parse unchecked tasks and explicit deferred records.** [depends: 4.35] [evidence: fixture tests]
- [x] **4.37 Parse validation evidence rows and required command matrix.** [depends: 4.35] [evidence: tests]
- [x] **4.38 Fail when tasks are checked but validation says pending/not run.** [depends: 4.37] [evidence: negative test]
- [x] **4.39 Fail when a completion-ready change has unchecked non-deferred tasks.** [depends: 4.36] [evidence: negative test]
- [x] **4.40 Fail archival readiness when required evidence is absent.** [depends: 4.36, 4.37] [evidence: test]
- [x] **4.41 Add verifier to CI and `verify-hardening`.** [depends: 4.35–4.40] [evidence: workflow/Make test]
- [x] **4.42 Reconcile existing active/archived OpenSpecs whose task/evidence state is inconsistent, without falsifying execution history.** [depends: 4.35] [evidence: reconciliation report]
- [x] **4.43 Document required GitHub branch-protection checks and merge policy.** [depends: 4.23–4.41] [evidence: docs]

## Phase 4 gate

- [x] **4.G1 Run fixture-contract eval from source checkout.** [depends: 4.2, 4.5–4.9]
- [x] **4.G2 Run runtime-replay eval with all seed/negative cases.** [depends: 4.11–4.22]
- [x] **4.G3 Run installed wheel/sdist/deb evaluation.** [depends: 4.7–4.10]
- [ ] **4.G4 Run complete CI-equivalent command matrix locally or in CI.** [depends: 4.23–4.34]
- [ ] **4.G5 Run OpenSpec completion verifier against this change.** [depends: 4.35–4.42]
- [ ] **4.G6 Record Phase 4 PASS in `validation.md`.** [depends: 4.G1–4.G5]

# 5. Documentation, migration, and operator experience

- [x] **5.1 Update architecture/package-boundary docs for transactional workspace and prepared turns.** [depends: Phase 1–2]
- [x] **5.2 Update workspace lifecycle docs for root migration, status state machine, locking, compaction, redaction, export, and repair.** [depends: Phase 1]
- [x] **5.3 Update assistant docs for untrusted context, store_raw, prepare/execute, and plan approval identity.** [depends: Phase 2]
- [x] **5.4 Update data availability docs for strict dates, cache eligibility, and lock semantics.** [depends: Phase 3]
- [x] **5.5 Update model routing docs for session isolation.** [depends: 3.26–3.28]
- [x] **5.6 Update TUI help/docs for `/new`, `/chat new`, busy behavior, workspace recovery, and TODO visibility.** [depends: 2.28–2.36, 3.23–3.25]
- [x] **5.7 Update eval docs for fixture-contract vs runtime-replay and installed-package behavior.** [depends: Phase 4]
- [x] **5.8 Add migration guide for tracked runtime files and legacy workspace roots.** [depends: 1.3–1.20]
- [x] **5.9 Add rollback notes and feature flags only where necessary; do not preserve unsafe behavior as default.** [evidence: docs/review]

# 6. Final validation and completion

- [x] **6.1 Run `make repo-hygiene`.** [depends: 1.G5]
- [x] **6.2 Run focused Phase 1 workspace/repository tests.** [depends: 1.G5]
- [x] **6.3 Run focused Phase 2 context/prepared-turn/TUI tests.** [depends: 2.G5]
- [x] **6.4 Run focused Phase 3 correctness tests.** [depends: 3.G5]
- [x] **6.5 Run `make lint-vnalpha`.** [depends: 4.1]
- [ ] **6.6 Run `make test-vnalpha`.**
- [x] **6.7 Run `make verify-r4`.**
- [x] **6.8 Run `packaging/scripts/openstock-verify --ci`.**
- [x] **6.9 Run `make eval-research-answers`.** [depends: 4.G1]
- [x] **6.10 Run `make eval-research-runtime`.** [depends: 4.G2]
- [x] **6.11 Run installed-package evaluation.** [depends: 4.G3]
- [ ] **6.12 Run `python scripts/check-openspec-completion.py openspec/changes/openstock-four-phase-hardening`.** [depends: 4.G5]
- [ ] **6.13 Confirm required GitHub checks pass on final implementation SHA.** [depends: 4.G4]
- [ ] **6.14 Confirm no unresolved P0/P1 finding from `review.md` remains without an approved deferred record.**
- [ ] **6.15 Confirm every checked task has evidence and every incomplete task remains unchecked.**
- [ ] **6.16 Mark implementation ready for review/archive only after 6.1–6.15 pass.**

## Final definition of done

```text
All four phase gates PASS.
All final validation commands exit 0.
No denied tracked runtime/generated artifacts remain.
Workspace and data locks pass multi-process tests.
Context trust and exact-plan execution tests pass.
Runtime and installed-package evaluations pass.
OpenSpec verifier reports consistent completion evidence.
Required GitHub checks are green on the final SHA.
```
