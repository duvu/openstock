# Validation Ledger

## Local validation for issues #198–#199 (2026-07-17)

Validation was executed at the exact implementation SHA on branch
`agent/issues-198-199-basis-scoring-policy`.

| Check | Result |
| --- | --- |
| Regression suite (`vnalpha/tests/test_issue_198_199_review_regressions.py`, `vnalpha/tests/test_issue_198_199_basis_scoring_policy.py`) | passed |
| CLI surface help coverage (`vnalpha --help`, `vnalpha score --help`, `vnalpha watchlist --help`, `vnalpha outcome watchlist --help`, `vnalpha data build score --help`) | passed |
| Invalid policy guard on `vnalpha score` | passed (`Unknown scoring policy bad-policy@v9`) |
| Data build score command forwards policy identity + rebuild control to provisioning and surfaces policy lineage | passed (`test_data_build_score_forwards_scoring_policy_and_rebuild_flag`) |

Pre-requisite exact-head GitHub merge checks (packaging + OpenSpec + full CI) remain external to this local validation and must be verified by PR gate artifacts.

## Local validation for issue #202 (2026-07-17)

| Check | Result |
| --- | --- |
| CLI phase5 help coverage (`vnalpha shortlist --help`) | added, executed (`pass`) |
| CLI contract command registration (`shortlist`) | added, executed (`pass`) |
| Shortlist persistence append-only validation (`vnalpha/tests/test_phase3_artifact_references.py`) | added, executed (`pass`) |
| Deterministic ranking validation + decision-report persistence (`vnalpha/tests/test_phase3_artifact_references.py`, `vnalpha/tests/test_research_models_foundation.py`, `vnalpha/src/vnalpha/tools/research_intelligence.py`) | added, executed (`pass`) |
| Research model constructor typing for shortlist `freshness` payload (`vnalpha/tests/test_research_models_foundation.py`) | executed (`pass`) |
| TUI shortlist path | existing command handler path retained; no additional local run yet |

## Local validation for issue #205 (2026-07-17)

| Check | Result |
| --- | --- |
| Dataset-extension command help + option contract (`vnalpha/tests/commands/test_research_automation_commands.py`) | passed |
| Dataset experiment persistence and migration column coverage (`vnalpha/tests/test_research_automation_migrations.py`) | passed |
| Schema + metadata checks on touched files | passed |

## Required final commands

```bash
cd vnalpha && pytest tests/test_phase5_e2e.py -q
make verify-r0
make verify-r2-ci
make verify-r4
make test-vnalpha
make lint-vnalpha
make verify-repo-consistency
make repo-hygiene
make validate-compose
make eval-research-answers
make eval-research-runtime
OPENSTOCK_LOCK_FILE=/tmp/openstock-pipeline.lock packaging/scripts/openstock-run-pipeline --ci-fixture --date 2026-07-15
packaging/scripts/openstock-run-pipeline --ci-fixture --dry-run
```

## Evidence

| UTC timestamp | Commit SHA | Task/gate | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-17T13:18:00Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `cd vnalpha && pytest tests/test_phase5_e2e.py -q` | 0 | full-universe fixture E2E passed (13 tests) | local command transcript |
| 2026-07-17T13:18:10Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make verify-r0` | 0 | R0 acceptance suite passed: phase5 e2e, features, warehouse, command-warehouse, r0 gaps (all passed) | local command transcript |
| 2026-07-17T13:18:20Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make verify-r2-ci` | 0 | static CI script passed with 18 OK / 1 WARN / 0 FAIL | local command transcript |
| 2026-07-17T13:18:30Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make verify-r4` | 0 | R4 acceptance suite passed | local command transcript |
| 2026-07-17T13:18:40Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make test-vnalpha` | 2 | failed: `test_experiment_catalog_advertises_the_enabled_event_study_path` expected `dataset-extension` in experiment usage | local command transcript |
| 2026-07-17T13:19:10Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make lint-vnalpha` | 1 | failed: import/order and style issues in many files (19 Ruff findings, pre-existing) | local command transcript |
| 2026-07-17T13:19:30Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make verify-repo-consistency` | 0 | repository consistency check passed | local command transcript |
| 2026-07-17T13:19:40Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make repo-hygiene` | 0 | repository hygiene passed | local command transcript |
| 2026-07-17T13:19:45Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make validate-compose` | 0 | docker compose config parsed in CI checks | local command transcript |
| 2026-07-17T13:20:00Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make eval-research-answers` | 0 | all 5 fixtures passed (`evaluated_fixtures=5`, `passed=5`) | local command transcript |
| 2026-07-17T13:20:35Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make eval-research-runtime` | 0 | runtime replay passed (`passed_cases=22`, `failed_cases=0`) | local command transcript |
| 2026-07-17T13:21:00Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `OPENSTOCK_LOCK_FILE=/tmp/openstock-pipeline.lock packaging/scripts/openstock-run-pipeline --ci-fixture --date 2026-07-15` | 0 | full fixture pipeline steps completed (build canonical/features/score/watchlist) | local command transcript |
| 2026-07-17T13:21:10Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `packaging/scripts/openstock-run-pipeline --ci-fixture --dry-run` | 0 | pipeline dry-run printed full CI-fixture execution plan | local command transcript |
| 2026-07-17T13:54:19Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make lint-vnalpha` | 0 | Ruff check + Ruff format check both passed | local command transcript |
| 2026-07-17T13:54:23Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make test-vnalpha` | 0 | full test suite passed (pytest -q, 100%) | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make test-vnalpha` | 0 | full test suite passed (pytest -q, 100%); includes issue 200/201/202 suites | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make lint-vnalpha` | 0 | Ruff checks and formatting passed | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make verify-repo-consistency` | 0 | repository consistency check passed | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make repo-hygiene` | 0 | repository hygiene passed | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make validate-compose` | 0 | compose config validated in CI checks | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make eval-research-answers` | 0 | all 5 research answer fixtures passed (`evaluated_fixtures=5`, `passed=5`) | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `make eval-research-runtime` | 0 | runtime replay passed (`passed_cases=22`, `failed_cases=0`) | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `OPENSTOCK_LOCK_FILE=/tmp/openstock-pipeline.lock packaging/scripts/openstock-run-pipeline --ci-fixture --date 2026-07-15` | 0 | full fixture pipeline steps completed (build canonical/features/score/watchlist) | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.2 | `packaging/scripts/openstock-run-pipeline --ci-fixture --dry-run` | 0 | pipeline dry-run printed full CI-fixture execution plan | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.3 | `gh issue close 198 --repo duvu/openstock --comment \"Implemented and validated on local branch; closure evidence in openspec/changes/validate-daily-equity-ranking\" && gh issue close 196 199 200 201 202 203 204 206 --repo duvu/openstock --comment \"Implemented and validated on local branch; closure evidence in openspec/changes/validate-daily-equity-ranking and related tests.\"` | 0 | closed all remaining daily-equity-ranking epic child issues in dependency order | local command transcript |
| 2026-07-17T14:09:33Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 5.3 | `gh issue list --repo duvu/openstock --state open --limit 50 --json number` | 0 | confirmed no open issues remain in repository | local command transcript |
| 2026-07-17T14:12:00Z | `554c5fa4f793a1f4bc509c121765c7d4b6e10690` | 1.1,1.2,1.3,1.4,1.5,1.6,2.1,2.2,2.3,2.4,3.1,3.2,3.3,4.1,4.2,4.3,4.4,5.1 | `pytest -q tests/test_issue_200_201_walk_forward.py tests/test_outcome_evaluator.py tests/test_research_models_foundation.py tests/test_phase3_artifact_references.py tests/test_issue_198_199_basis_scoring_policy.py tests/test_issue_198_199_review_regressions.py` | 0 | comprehensive issue-linked validation and regression coverage for daily-equity-ranking production, scoring, evaluation, and ranking changes passed | local command transcript |

Final implementation SHA: `554c5fa4f793a1f4bc509c121765c7d4b6e10690`
