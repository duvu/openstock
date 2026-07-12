# Validation: OpenStock four-phase hardening

## Status

```text
OpenSpec authored: yes
Runtime implementation: Phase 1–2 evidence is present; Phase 3 tasks 3.1–3.32 are implemented in the working tree; Phase 4 lint, Make targets, packaged-resource, and runtime-replay subgates have evidence
Validation commands executed: baseline, Phase 1–3 focused gates, Ruff, hygiene, secret-scan, package-resource, runtime-replay, CLI, and Make-target commands
Phase gates: Phase 1 implementation evidence exists but the current shared-worktree hygiene gate requires rerun; Phase 2 PASS; Phase 3 PASS; Phase 4 partial (CI/OpenSpec/final gates pending)
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
| 2026-07-12T01:13:00Z | `81330020b048ce3aab8671776ecc12f17c8ab7bf` + working tree | 1.12 | `packaging/scripts/openstock-secret-scan --history` | 0 | Reachable history at the baseline contained no scanner matches; no history rewrite was required by that scan | local command transcript |
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
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | 3.22, 3.25–3.28, 3.G3 | `pytest -q tests/commands/test_context_commands.py tests/workspace_context/test_compaction.py tests/workspace_context/test_retention.py tests/workspace_context/test_lifecycle_e2e.py tests/test_tui_todo_panel.py tests/test_chat_controller.py tests/test_chat_local_commands.py tests/test_command_parser.py tests/test_model_routing.py tests/commands/test_model_commands.py` | 0 | Real `/context compact`, `/new`/`/chat new`, TODO visibility transitions, session override isolation/cleanup, model scope reporting, and workspace lifecycle tests passed | local command transcript |
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | 3.G4 | `pytest -q tests/test_phase3_data_lock_and_dates.py tests/test_data_availability_checks.py tests/test_data_availability_integration.py tests/test_phase3_cache_eligibility.py tests/test_assistant_lifecycle_hardening.py tests/test_synthesizer_and_app.py tests/test_intent_and_planner.py tests/test_evals_runtime_runner.py tests/test_evals_runtime_report.py tests/test_tui_todo_panel.py tests/test_tui_todo_refresh.py tests/test_tui_workspace.py tests/test_tui_command.py tests/test_model_routing.py tests/commands/test_model_commands.py tests/commands/test_context_commands.py tests/workspace_context -rA` | 0 | Every selected data-availability, assistant, runtime-eval, TUI, model-routing, command, and workspace regression test reported PASS | local command transcript |
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | 3.G5 | validation ledger update after 3.G3/3.G4 | 0 | Phase 3 matrix is now complete and records PASS for every required gate | this file |
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | 4.1 | `make lint-vnalpha` | 0 | Ruff check passed; all 456 files passed format check | local command transcript |
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | 4.2, 6.9 | `make eval-research-answers` | 0 | Fixture-contract evaluation passed 5/5 evaluated cases with zero operational/check failures | local command transcript |
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | 4.3, 4.21, 4.22, 6.10 | `make eval-research-runtime` | 0 | Runtime replay passed 10/10 cases with zero failures and stable human-readable output | local command transcript |
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | 4.5–4.7, 4.11–4.20 | `pytest -q tests/test_evals_runtime_loader.py tests/test_evals_cli.py tests/test_evals_package_resources.py tests/test_evals_runtime_runner.py tests/test_evals_runtime_report.py -rA` | 0 | 17 tests passed: strict typed runtime schema/loader, package resource and wheel corpus checks, production-boundary replay, exact-plan/check assertions, network prohibition, all-intent coverage, negative cases, invalid date, claim mapping, CLI, and reports | local command transcript |
| 2026-07-12T05:39:49Z | `2365e9a77c6cff8fd6f1d4c8428ded32833f7ebe` + working tree | manual QA for 3.23–3.24, 4.21 | `PYTHONPATH=src python -c 'from vnalpha.cli import app; app()' eval research-runtime --help`; isolated `CommandExecutor` driver for `/new --no-compact` and `/chat new` | 0 | CLI help exposes `--ci`/`--json`; `/new` resolves to `/context new`; `/chat new` returns a chat-session metadata ID; temporary workspace was removed | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.8, 4.10, 4.G3 | `./packaging/build-deb.sh --offline --output-dir /tmp/openstock-deb-test` followed by `./packaging/test/test_packaging.sh /tmp/openstock-deb-test/vnalpha_0.1.0_amd64.deb` | 0 | Fresh offline Debian fixture passed 54 checks; it bundles the application wheel and runtime resources, then runs both fixture-contract and runtime-replay evals from the extracted wheel | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.9, 4.G3 | `pytest -q tests/test_evals_package_resources.py -rA` | 0 | 3 tests passed: package resources, wheel contents, and isolated installed-wheel CLI evaluations for both eval modes | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.7, 4.G3 | `python -m build --sdist --no-isolation --outdir /tmp/openstock-sdist` and archive inspection | 0 | sdist built successfully and contains all 10 golden YAML and 10 runtime JSON resources | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.4 | `make -n verify-hardening` | 0 | Target expands in deterministic order: hygiene, secret scan, lint, R0/R2/full tests, R4, packaging verification, both evals, and OpenSpec verifier | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.23–4.26, 4.34 | workflow YAML inspection and parse; `python -c 'import yaml; ...'` | 0 | CI starts with hygiene/secret scan, uploads focused/lint/packaging/eval diagnostics, orders Ruff before full tests, and cancels only pull-request runs | local command transcript and workflow diff |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.35–4.40 | `pytest -q scripts/tests/test_check_openspec_completion.py -rA` | 0 | 7 verifier fixture tests passed for complete state, completion-ready unchecked tasks, pending validation, malformed evidence, structured defers, missing required command evidence, and archived incomplete evidence | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.G5 | `python scripts/check-openspec-completion.py openspec/changes/openstock-four-phase-hardening` | 1 | Correctly reports the active change incomplete because 14 tasks remain unchecked, required final commands lack successful evidence, and phase gates remain pending | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.27 | `make test-vnalpha` | 1 | Collection now completes; 10 existing failures remain from research-intent/table-count expectations, provider-backed command assumptions, slash persistence baseline, and sandbox/prepared schema additions; the task remains unchecked | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.27 regression isolation | `pytest -q tests/workspace_context/test_locking.py::test_concurrent_input_mutations_are_not_lost tests/test_r4_controller_persistence.py::TestSlashCommandPersistence::test_slash_command_result_persisted tests/test_chat_controller.py -rA` | 0 | Importlib test collection compatibility and session-scoped executor compatibility regressions pass after targeted fixes | local command transcript |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 5.1–5.9 | documentation inspection | 0 | `vnalpha/docs/four-phase-hardening.md` covers architecture, lifecycle/migration, assistant/data/model/TUI/eval contracts, rollback, and verifier operation and is linked from the docs map | documentation diff |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.43 | documentation inspection | 0 | `vnalpha/docs/branch-protection.md` documents the required `vnalpha-ci / validate` check, fail-closed merge policy, and PR-only workflow | documentation diff |
| 2026-07-12T06:03:33Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.42 | `openspec/reconciliation-report.md` inventory and review | 0 | Active and archived changes were inventoried; incomplete active work remains active, historical ledgers were not fabricated, and the P0 change remains the only completion candidate in this worktree | reconciliation report |
| 2026-07-12T06:06:15Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.28, 6.7 | `make verify-r4` | 0 | R4 acceptance suite passed all selected tests | local command transcript |
| 2026-07-12T06:06:15Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.29, 6.8 | `packaging/scripts/openstock-verify --ci` | 0 | 16 required checks passed, 1 environment warning was reported, and 0 checks failed; script status PASS | local command transcript |
| 2026-07-12T06:06:15Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 6.1 | `make repo-hygiene` | 1 | Current shared worktree still contains tracked denied runtime/egg-info paths and unapproved gitlinks from unrelated work; task remains unchecked | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 3.G4, 4.5–4.11, 4.21, 4.28, 4.34 | `pytest -q tests/test_evals_runtime_loader.py tests/test_evals_cli.py tests/test_evals_package_resources.py tests/test_evals_runtime_runner.py tests/test_evals_runtime_report.py tests/test_model_routing.py tests/commands/test_model_commands.py tests/test_tui_routing.py tests/test_r4_controller_persistence.py::TestSlashCommandPersistence::test_slash_command_result_persisted -rA` | 0 | 68 targeted runtime-eval, package, model-routing, TUI, and persistence tests passed | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.35–4.40 | `pytest -q scripts/tests/test_check_openspec_completion.py -rA` | 0 | 7 OpenSpec completion-verifier fixture tests passed | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.1 | `make lint-vnalpha` | 0 | Ruff check passed; 456 files passed format check | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.2, 6.9 | `make eval-research-answers` | 0 | 5/5 evaluated cases passed with zero operational/check failures | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.3, 4.21, 4.22, 6.10 | `make eval-research-runtime` | 0 | 10/10 runtime cases passed with zero failures | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.28, 6.7 | `make verify-r4` | 0 | R4 acceptance suite passed | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.29, 6.8 | `packaging/scripts/openstock-verify --ci` | 0 | 16 checks passed, 1 environment warning, 0 failures; script status PASS | local command transcript |
| 2026-07-12T06:39:24Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 1.11, 4.24 | `packaging/scripts/openstock-secret-scan` | 0 | Current worktree scan passed; the negative credential is assembled at fixture runtime and is not present in tracked source | local command transcript |
| 2026-07-12T06:39:24Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 1.12 | `packaging/scripts/openstock-secret-scan --history` | 1 | One historical match is the synthetic credential literal from an earlier negative-fixture revision; it is not a deployed credential, so no history rewrite is authorized or required | local command transcript |
| 2026-07-12T06:40:49Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.G5, 6.12 | `python scripts/check-openspec-completion.py openspec/changes/openstock-four-phase-hardening` | 1 | Correctly reports 21 unchecked tasks, pending gates, and missing successful full-test/verifier evidence after the current-tree hygiene tasks were reconciled | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 3.23–3.24, 4.21 | isolated CLI driver for `CommandExecutor.execute('/new --no-compact')` and `ChatController.handle_turn('/chat new')` | 0 | `/new` returned `SUCCESS` as `/context new`; `/chat new` created a session and emitted the expected message | local command transcript |
| 2026-07-12T06:19:50Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.G5, 6.12 | `python scripts/check-openspec-completion.py openspec/changes/openstock-four-phase-hardening` | 1 | Before the current hygiene-task reconciliation, correctly reported 14 unchecked tasks, pending gates, and missing successful full-test/verifier evidence | local command transcript |
| 2026-07-12T06:34:40Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 4.27, 4.G4, 6.6 | `make test-vnalpha` | 2 | Collection completes; 8 failures remain in dirty-baseline intent-set, migration/table-count, and provider-backed compare/explain expectations; the TUI callable-identity regression is fixed and passes its focused test | local command transcript |
| 2026-07-12T06:34:40Z | `39fe452bc6e81071928a6746e0189a9b569c3b33` + working tree | 3.G3, 4.28 | `pytest -q tests/test_tui_workspace.py::test_9_12_router_slash_command_routes_to_executor tests/test_tui_routing.py tests/test_model_routing.py -rA` | 0 | 24 focused TUI routing and model-routing tests passed after restoring direct executor-call compatibility | local command transcript |

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
| Denied tracked paths removed | `git ls-files` report | Fail (tracked denied paths remain in the shared worktree) |
| Unapproved gitlinks removed | `git ls-files --stage` report | Fail (unapproved gitlinks remain in the shared worktree) |
| Ignore rules verified | `git check-ignore -v` cases | Pass |
| Repository hygiene verifier | `make repo-hygiene` | Fail (shared worktree) |
| Secret/sensitive scan | scanner command/report | Pass |
| Deterministic workspace root | focused tests from multiple CWDs | Pass |
| Workspace lock exclusivity | multi-process tests | Pass |
| Lost-update prevention | concurrent mutation tests | Pass |
| Lifecycle invariants | create/archive/resume/new/status tests | Pass |
| Legacy migration | migration and backup tests | Pass |
| Retention/compaction | before/after/archive tests | Pass |
| Redaction/export | E2E sensitive-text test | Pass |
| Phase 1 result | all above | **PENDING — rerun after shared-worktree hygiene is resolved** |

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
| Real compaction command path | command E2E | Pass |
| `/new` namespace | parser/chat/TUI tests | Pass |
| TODO transition events | resize/toggle tests | Pass |
| Session override isolation | two-session test | Pass |
| Grounded source refs | missing-ref fallback tests | Pass |
| Phase 3 result | all above | **PASS** |

## Phase 4 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Ruff check/format | `make lint-vnalpha` | Pass |
| Root eval targets | Make target tests | Pass |
| Packaged corpus | wheel package-resource inspection | Pass |
| Installed wheel eval | isolated install command | Pass |
| Debian/package eval | package test or approved defer | Pass |
| Fixture-contract eval | `make eval-research-answers` | Pass |
| Runtime-replay eval | `make eval-research-runtime` | Pass |
| Runtime replay covers all research intents | report and corpus test | Pass |
| Negative runtime cases | report and corpus test | Pass |
| Network prohibited | network-guard test | Pass |
| Repository hygiene in CI | workflow run | Pending |
| Secret scan in CI | workflow run | Pending |
| Full tests | `make test-vnalpha` | Fail (shared dirty baseline) |
| R4 | `make verify-r4` | Pass |
| Packaging verify | `packaging/scripts/openstock-verify --ci` | Pass |
| OpenSpec verifier | script command | Fail (active change incomplete) |
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
- Repository-wide gate 4.27/6.6: the post-fix `make test-vnalpha` run collects successfully with importlib mode and `tests/` on the spawned-worker path, but 8 failures remain in persisted research-intent expectations, legacy migration table counts, provider-backed compare/explain assumptions, and warehouse schema expectations. The TUI callable-identity compatibility regression introduced in this slice is fixed and its focused tests pass; the full task remains unchecked.
- Repository hygiene gate 6.1: the shared worktree still exposes tracked `.vnalpha/`, `vnalpha/.vnalpha/`, `.worktrees/`, and `vnalpha/src/vnalpha.egg-info/` paths, including unrelated generated workspace state. They are preserved per repository collaboration instructions and require an owner-controlled index cleanup before this gate can pass.
- Whole-change strict OpenSpec validation: four existing requirement sections outside this runtime-correctness slice lack requirement prose (`Public command and operational event semantics`, `Evaluation shall support fixture-contract and runtime-replay modes`, `Root commands and CI shall enforce all hardening gates`, and `Final hardening validation shall pass as one reproducible gate`). Their owners must add requirement text before task 3.G5/final validation; this slice did not edit those sections.

## Next executable task

```text
Task 4.27 — reconcile the remaining repository-wide failures with the active dirty research/sandbox feature baseline, then rerun the complete CI-equivalent matrix. Packaging, runtime replay, docs, and verifier subgates are already evidenced; leave 0.2/0.3/0.6 and external GitHub/owner decisions unchanged.
```

## Completion record

```text
Final implementation SHA: Pending
Final CI run: Pending
OpenSpec verifier result: Pending
Ready to archive: No
```
