# Validation: OpenStock four-phase hardening

## Status

```text
OpenSpec authored: yes
Runtime implementation: Phase 1–2 evidence is present; Phase 3 runtime-correctness tasks 3.1–3.21 and 3.29–3.31 are implemented in the working tree; remaining Phase 3 tasks are pending
Validation commands executed: baseline, Phase 1–2, Phase 3 focused runtime-correctness, Ruff, hygiene, and secret-scan commands
Phase gates: pending
```

This file is the evidence ledger. Do not replace `pending` with `pass` without attaching exact command evidence for the tested commit.

## Baseline

| Field | Value |
|---|---|
| Baseline branch | `main` |
| Baseline commit | `81330020b048ce3aab8671776ecc12f17c8ab7bf` (`main`) |
| OpenSpec branch | `agent/openstock-four-phase-hardening-openspec` (merged by PR #44) |
| Runtime implementation PRs | Draft PR #48: https://github.com/duvu/openstock/pull/48 |
| Latest required-check result | Failed on main run #29158043342: focused assistant research-intelligence tests |

## Baseline evidence (tasks 0.1–0.4)

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-12T01:11:33Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.1 | `git rev-parse HEAD && git branch --show-current && git remote -v` | 0 | `main` at baseline SHA; origin is `github.com:duvu/openstock.git` | local command transcript |
| 2026-07-12T01:11:33Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.1 | `git ls-files | rg '(^|/)(\\.vnalpha|vnalpha/\\.vnalpha|\\.worktrees)(/|$)|\\.egg-info(/|$)|__pycache__(/|$)|\\.pytest_cache(/|$)|\\.ruff_cache(/|$)|\\.pyc$'` | 0 | 24 denied tracked paths found, including two mode-160000 `.worktrees` entries | local command transcript |
| 2026-07-12T01:11:33Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.1 | `git ls-files --stage | awk '$1 == "160000" {print}'` | 0 | Two unapproved gitlinks: `.worktrees/market-regime-and-sector-context` and `.worktrees/research-answer-evaluation-golden-set` | local command transcript |
| 2026-07-12T01:11:33Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.1 | `gh pr list --state all --search 'hardening' --limit 20 --json number,title,state,url,headRefName,baseRefName` | 0 | Draft PR #48 is the only open runtime-hardening PR; PR #44 is merged OpenSpec documentation | https://github.com/duvu/openstock/pull/48 |
| 2026-07-12T01:11:33Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.1 | `gh run view 29158043342 --json conclusion,jobs,url,headSha,workflowName` | 0 | Main CI failed at focused assistant research-intelligence tests; later gates were skipped | https://github.com/duvu/openstock/actions/runs/29158043342 |
| 2026-07-12T01:12:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.5 | `pytest -q tests/test_cli.py tests/test_cli_contract.py tests/test_policy_capabilities.py tests/test_safety_boundary.py` | 0 | 31 passed; research-only safety boundary remains enforced | local command transcript |
| 2026-07-12T01:12:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.6 | `pytest -q tests/test_assistant_models.py tests/test_synthesizer_and_app.py tests/test_tools.py tests/workspace_context/test_models.py tests/workspace_context/test_lifecycle.py` | 1 | 2 pre-existing failures from unrelated dirty research-feature changes: supported intent set drift and synthesizer prompt contract | local command transcript |
| 2026-07-12T01:11:26Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` | 0.6 | `pytest -q tests/test_cli.py tests/test_cli_contract.py tests/test_policy_capabilities.py tests/test_safety_boundary.py tests/test_assistant_persistence.py` | 1 | 31 passed, 1 pre-existing migration failure: 26 tables observed versus legacy assertion of 23 after sandbox schema additions | local command transcript |
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.1 | `git check-ignore -v .vnalpha/workspaces/index.json vnalpha/.vnalpha/workspaces/index.json .worktrees/example vnalpha/src/vnalpha.egg-info/PKG-INFO vnalpha/src/vnalpha/__pycache__/module.pyc vnalpha/tests/.pytest_cache/CACHEDIR.TAG vnalpha/.ruff_cache/cache.db` | 0 | All denied examples resolve to ignore rules | local command transcript |
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.2–1.6 | `git rm -r --cached --ignore-unmatch .vnalpha vnalpha/.vnalpha .worktrees vnalpha/src/vnalpha.egg-info`; followed by `git ls-files`/local-copy checks | 0 | 24 denied tracked paths and 2 gitlinks removed from the index; local workspace/worktree paths remained present | local command transcript |
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.7–1.9 | `bash packaging/tests/test_repo_hygiene.sh` | 0 | Clean fixture passes, seeded denied path fails, unapproved gitlink fails, exact allowlisted gitlink passes | local command transcript |
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.10 | `make repo-hygiene` | 0 | Root target invokes verifier and current index passes | local command transcript |
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.11 | `bash packaging/tests/test_repo_secret_scan.sh && packaging/scripts/openstock-secret-scan` | 0 | Seeded high-signal credential fails fixture scan; current tracked files pass | local command transcript |
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.12 | `packaging/scripts/openstock-secret-scan --history` | 0 | Reachable Git history contains no scanner matches; no history rewrite is required by this scan | local command transcript |
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.13 | `make repo-hygiene; packaging/scripts/openstock-secret-scan; bash packaging/tests/test_repo_hygiene.sh; bash packaging/tests/test_repo_secret_scan.sh` in `.github/workflows/vnalpha-ci.yml` | 0 | CI preparation now runs both scanners and both recurrence fixtures before dependency installation | workflow diff and local command transcript |
| 2026-07-12T02:10:32Z | baseline + working tree | 1.14–1.20 | `pytest -q tests/workspace_context/test_storage.py tests/workspace_context/test_migration.py tests/workspace_context/test_recovery.py`; docs inspection | 0 | Platform state root, explicit/env precedence, CWD invariance, legacy detection/migration, checksum backup, malformed-state quarantine, and repair documentation pass | local command transcript; workspace lifecycle docs |
| 2026-07-12T02:10:32Z | baseline + working tree | 1.21–1.33 | `pytest -q tests/workspace_context/test_locking.py tests/workspace_context/test_task_mutations.py tests/workspace_context/test_storage.py` | 0 | Atomic metadata lock, owner-safe release, timeout/stale replacement, transaction boundary, and repeated multi-process lost-update tests pass | local command transcript |
| 2026-07-12T02:10:32Z | baseline + working tree | 1.34–1.43 | `pytest -q tests/workspace_context/test_models.py tests/workspace_context/test_lifecycle.py tests/workspace_context/test_lifecycle_e2e.py tests/workspace_context/test_migration.py` | 0 | Versioned status, explicit activation, archive/reactivate, pointer recovery, read-only status, new-workspace lifecycle, and invariant checks pass | local command transcript |
| 2026-07-12T02:10:32Z | baseline + working tree | 1.44–1.52 | `pytest -q tests/workspace_context/test_retention.py tests/workspace_context/test_compaction.py` | 0 | Configurable bounds, archive rotation/checksums, preservation, measurable compaction, and duplicate-archive idempotency pass | local command transcript |
| 2026-07-12T02:10:32Z | baseline + working tree | 1.53–1.63 | `pytest -q tests/workspace_context/test_redaction.py tests/workspace_context/test_context_files.py tests/workspace_context/test_export.py` | 0 | Canonical redaction, safe projections, versioned export, path/symlink filtering, history exclusion, and task/error end-to-end export redaction pass | local command transcript |
| 2026-07-12T02:18:29Z | baseline + working tree | 2.1–2.8 | `pytest -q tests/test_assistant_lifecycle_hardening.py tests/test_assistant_research_intelligence_completion.py tests/test_synthesizer_and_app.py` | 0 | Typed request separation, bounded untrusted context, current-request-only classifier/safety path, lower-trust synthesis context, and compatibility prompt contracts pass | local command transcript |
| 2026-07-12T02:18:29Z | baseline + working tree | 2.9–2.14 | `pytest -q tests/test_assistant_lifecycle_hardening.py tests/test_assistant_persistence.py` | 0 | Prompt summary/hash/length/context-reference projection, redacted raw-storage opt-in, and additive warehouse migration/read compatibility pass | local command transcript |
| 2026-07-12T02:18:29Z | baseline + working tree | 2.15–2.27 | `pytest -q tests/test_assistant_lifecycle_hardening.py tests/test_plan_approval.py tests/test_r4_controller_persistence.py tests/test_r4_permissions.py` | 0 | Prepared-turn identity, exact execution, hash mismatch, cancellation, approval compatibility, and observability paths pass | local command transcript |
| 2026-07-12T02:18:29Z | baseline + working tree | 2.28–2.36 | `pytest -q tests/test_tui_routing.py tests/workspace_context/test_recovery.py tests/commands/test_context_commands.py` | 0 | Busy rejection before persistence, best-effort hook failure, malformed-state quarantine, temporary recovery, and `/context repair` behavior pass | local command transcript |
| 2026-07-12T02:44:35Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 3.1–3.16, 3.G1 | `uv run pytest tests/test_phase3_data_lock_and_dates.py tests/test_phase3_cache_eligibility.py tests/test_data_availability_checks.py tests/test_data_availability_ensure.py tests/test_data_availability_lock_and_observability.py tests/test_data_availability_service_split.py tests/test_data_availability_integration.py tests/test_dates.py tests/test_command_parser.py` | 0 | 123 passed; atomic/stale/owner-safe locking, context contention, symbol/date path containment, exception release, strict date zero-side-effect behavior, cache eligibility/reasons, and fast no-action cache hit pass | `.omo/evidence/openstock-four-phase-hardening-phase3-runtime-correctness/final-data-pytest-definitive.log` |
| 2026-07-12T02:44:35Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 3.17–3.21, 3.29–3.31, 3.G2 | `uv run pytest tests/test_phase3_artifact_references.py tests/test_phase3_grounded_source_refs.py tests/test_assistant_research_intelligence_completion.py tests/test_research_answer_audit_completion.py tests/test_research_policy_rewrite_completion.py tests/test_research_tool_execution_completion.py tests/test_research_context_tools.py tests/test_research_context_review_findings.py tests/test_synthesizer_and_app.py tests/test_tools.py` | 0 | 130 passed; query-backed refs, shortlist/deep-symbol missing-sector disclosure, audit integrity, missing-model-ref fallback, bounded refs, and optional claim mapping pass | `.omo/evidence/openstock-four-phase-hardening-phase3-runtime-correctness/final-research-pytest-definitive.log` |
| 2026-07-12T02:44:35Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 3.G1–3.G2 | `uv run ruff check src/vnalpha/data_availability/__init__.py src/vnalpha/data_availability/cache.py src/vnalpha/data_availability/checks.py src/vnalpha/data_availability/dates.py src/vnalpha/data_availability/ensure.py src/vnalpha/data_availability/lock.py src/vnalpha/data_availability/models.py src/vnalpha/data_availability/observability.py src/vnalpha/data_availability/planner.py src/vnalpha/data_availability/policy.py src/vnalpha/data_availability/results.py src/vnalpha/data_availability/service.py src/vnalpha/tools/artifact_references.py src/vnalpha/tools/research_intelligence.py src/vnalpha/assistant/groundedness.py src/vnalpha/assistant/models.py src/vnalpha/assistant/response_parser.py src/vnalpha/assistant/synthesizer.py tests/test_phase3_data_lock_and_dates.py tests/test_phase3_cache_eligibility.py tests/test_phase3_artifact_references.py tests/test_phase3_grounded_source_refs.py tests/test_data_availability_checks.py tests/test_data_availability_ensure.py tests/test_data_availability_lock_and_observability.py tests/test_assistant_research_intelligence_completion.py tests/test_synthesizer_and_app.py` | 0 | All checks passed across 27 scoped files | `.omo/evidence/openstock-four-phase-hardening-phase3-runtime-correctness/final-ruff-check-definitive.log` |
| 2026-07-12T02:44:35Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 3.G1–3.G2 | `uv run ruff format --check src/vnalpha/data_availability/__init__.py src/vnalpha/data_availability/cache.py src/vnalpha/data_availability/checks.py src/vnalpha/data_availability/dates.py src/vnalpha/data_availability/ensure.py src/vnalpha/data_availability/lock.py src/vnalpha/data_availability/models.py src/vnalpha/data_availability/observability.py src/vnalpha/data_availability/planner.py src/vnalpha/data_availability/policy.py src/vnalpha/data_availability/results.py src/vnalpha/data_availability/service.py src/vnalpha/tools/artifact_references.py src/vnalpha/tools/research_intelligence.py src/vnalpha/assistant/groundedness.py src/vnalpha/assistant/models.py src/vnalpha/assistant/response_parser.py src/vnalpha/assistant/synthesizer.py tests/test_phase3_data_lock_and_dates.py tests/test_phase3_cache_eligibility.py tests/test_phase3_artifact_references.py tests/test_phase3_grounded_source_refs.py tests/test_data_availability_checks.py tests/test_data_availability_ensure.py tests/test_data_availability_lock_and_observability.py tests/test_assistant_research_intelligence_completion.py tests/test_synthesizer_and_app.py` | 0 | 27 scoped files already formatted | `.omo/evidence/openstock-four-phase-hardening-phase3-runtime-correctness/final-ruff-format-definitive.log` |
| 2026-07-12T02:44:35Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 3.1–3.21, 3.29–3.31 | `uv run python ../.omo/evidence/openstock-four-phase-hardening-phase3-runtime-correctness/manual_phase3_probe.py` (from `vnalpha/`) | 0 | Library probe reports `status=PASS`, one of two lock owners, stale-owner safety, contended-context rejection, crafted symbol/date containment, zero date side effects, no invented sector ref, and bounded deterministic fallback refs | `.omo/evidence/openstock-four-phase-hardening-phase3-runtime-correctness/manual-qa-definitive.log` |
| 2026-07-12T02:49:35Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | whole-change strict validation (not 3.G1/3.G2) | `openspec validate openstock-four-phase-hardening --type change --strict --no-interactive` | 1 | Four pre-existing requirement-text errors remain in out-of-scope Phase 3D/Phase 4 specification sections; in-scope task implementation and focused gates are unaffected | `.omo/evidence/openstock-four-phase-hardening-phase3-runtime-correctness/final-openspec-validate.log` |

## Evidence row format

Every executed command must add one row:

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| Pending | Pending | Pending | Pending | — | Not executed | — |

Rules:

```text
- timestamp must be UTC
- commit SHA must be the code that was tested
- command must be exact and reproducible
- exit is numeric
- summary includes pass/fail counts or concise outcome
- artifact is CI run/job/log, local attached log, or committed report
```

## Phase 1 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Denied tracked paths removed | `git ls-files` report | Pass |
| Unapproved gitlinks removed | `git ls-files --stage` report | Pass |
| Ignore rules verified | `git check-ignore -v` cases | Pass |
| Repository hygiene verifier | `make repo-hygiene` | Pass |
| Secret/sensitive scan | scanner command/report | Pass |
| Deterministic workspace root | focused tests from multiple CWDs | Pass |
| Workspace lock exclusivity | multi-process tests | Pass |
| Lost-update prevention | concurrent mutation tests | Pass |
| Lifecycle invariants | create/archive/resume/new/status tests | Pass |
| Legacy migration | migration and backup tests | Pass |
| Retention/compaction | before/after/archive tests | Pass |
| Redaction/export | E2E sensitive-text test | Pass |
| Phase 1 result | all above | **PASS** |

## Phase 2 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Current prompt/context separation | message-construction tests | Pass |
| Historical context marked untrusted | prompt contract tests | Pass |
| Safety current-request only | malicious-context tests | Pass |
| Classification current-request only | intent isolation tests | Pass |
| `store_raw=false` | persistence tests | Pass |
| `store_raw=true` bounded behavior | persistence tests | Pass |
| Prepared turn built once | classifier/planner call-count tests | Pass |
| Exact plan execution | plan hash/identity tests | Pass |
| Auto execute single preparation | controller integration test | Pass |
| Approval executes stored plan | controller integration test | Pass |
| Busy request handling | headless TUI test | Pass |
| Workspace hook resilience | injected failure test | Pass |
| Corrupt workspace recovery | headless TUI recovery test | Pass |
| Phase 2 result | all above | **PASS** |

## Phase 3 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Atomic data lock | multi-process test | Pass |
| Owner-safe release/stale replacement | focused tests | Pass |
| Strict explicit dates | zero-side-effect invalid-date test | Pass |
| Cache eligibility | score/feature/canonical/benchmark/quality/lineage matrix | Pass |
| Cache rejection observability | event test | Pass |
| Verified artifact refs | research-tool matrix | Pass |
| Missing sector behavior | shortlist payload test | Pass |
| Real compaction command path | command E2E | Pending |
| `/new` namespace | parser/chat/TUI tests | Pending |
| TODO transition events | resize/toggle tests | Pending |
| Session override isolation | two-session test | Pending |
| Grounded source refs | missing-ref fallback tests | Pass |
| Phase 3 result | all above | **Pending** |

## Phase 4 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Ruff check/format | `make lint-vnalpha` | Pending |
| Root eval targets | Make target tests | Pending |
| Packaged corpus | wheel/sdist file inspection | Pending |
| Installed wheel eval | isolated install command | Pending |
| Debian/package eval | package test or approved defer | Pending |
| Fixture-contract eval | `make eval-research-answers` | Pending |
| Runtime-replay eval | `make eval-research-runtime` | Pending |
| Runtime replay covers all research intents | report | Pending |
| Negative runtime cases | report | Pending |
| Network prohibited | test | Pending |
| Repository hygiene in CI | workflow run | Pending |
| Secret scan in CI | workflow run | Pending |
| Full tests | `make test-vnalpha` | Pending |
| R4 | `make verify-r4` | Pending |
| Packaging verify | `packaging/scripts/openstock-verify --ci` | Pending |
| OpenSpec verifier | script command | Pending |
| Required checks/branch protection | documented settings/check run | Pending |
| Phase 4 result | all above | **Pending** |

## Final command matrix

Run from repository root on the final implementation SHA:

```bash
make repo-hygiene
make lint-vnalpha
make test-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
make eval-research-answers
make eval-research-runtime
python scripts/check-openspec-completion.py \
  openspec/changes/openstock-four-phase-hardening
```

Additional installed-package validation:

```bash
python -m build vnalpha
python -m venv /tmp/openstock-hardening-wheel
/tmp/openstock-hardening-wheel/bin/pip install vnalpha/dist/*.whl
/tmp/openstock-hardening-wheel/bin/vnalpha eval research-answers --ci
/tmp/openstock-hardening-wheel/bin/vnalpha eval research-runtime --ci
```

Exact commands may be adjusted to the repository packaging interface, but equivalent installed-package proof is mandatory.

## Deferred work register

No tasks are deferred at OpenSpec creation time.

Required defer format:

```text
Task ID:
Reason:
Owner:
Dependency:
Risk accepted until:
Approval reference:
```

A deferred task does not count as complete. The final gate may pass with a defer only if the normative spec explicitly permits it and approval is recorded.

## Blockers

- Tasks 0.2 and 0.3: the repository contains unrelated uncommitted sandbox/research-feature work, and the existing PR #48 is only a draft scaffold rather than the required phase-split implementation branches with named owners. Creating or assigning new external PR/owner state is not authorized by this local implementation request. Keep these tasks unchecked until the owner/freeze decision is recorded; independent local hardening work may continue without changing those files.
- Task 0.6: the compatibility probe is currently blocked by two pre-existing failures in unrelated dirty files (`tests/test_assistant_models.py::test_supported_intents_include_persisted_context_reviews` and `tests/test_synthesizer_and_app.py::TestAnswerSynthesizer::test_synthesizer_grounding_check`) plus the sandbox migration table-count assertion. Do not weaken or delete those tests.
- Whole-change strict OpenSpec validation: four existing requirement sections outside this runtime-correctness slice lack requirement prose (`Public command and operational event semantics`, `Evaluation shall support fixture-contract and runtime-replay modes`, `Root commands and CI shall enforce all hardening gates`, and `Final hardening validation shall pass as one reproducible gate`). Their owners must add requirement text before task 3.G5/final validation; this slice did not edit those sections.

## Next executable task

```text
Task 0.4 — use the existing validation row format for the first repository-hygiene command, then Task 1.1 — add denied runtime/generated paths to .gitignore.
```

## Completion record

```text
Final implementation SHA: Pending
Final CI run: Pending
OpenSpec verifier result: Pending
Ready to archive: No
```
