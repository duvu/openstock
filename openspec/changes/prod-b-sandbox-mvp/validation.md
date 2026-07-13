# Validation: Sandboxed Compute MVP

Validation is recorded against base commit
`873425d62eb1aea7fc7519b62fde22ac195c7872` plus the dependency-closure
working tree.

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 0.1–0.6, 3.1–3.9 | `pytest -q tests/sandbox/test_static_guard.py tests/sandbox/test_static_guard_artifacts.py tests/test_safety_boundary.py tests/test_tool_policy.py` | 0 | Research-only boundary and static deny rules passed. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 1.1–1.7, 2.1–2.8, 5.1–5.6 | `pytest -q tests/sandbox/test_models.py tests/sandbox/test_storage.py tests/sandbox/test_artifact_writer.py tests/sandbox/test_output_validation.py` | 0 | Domain, storage, canonical artifact, and output-validation contracts passed. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 4.1–4.10, 9.1–9.6, 9.9 | `pytest -q tests/sandbox/test_docker_runner.py tests/sandbox/test_docker_runtime.py tests/sandbox/test_docker_orchestration.py tests/sandbox/test_execution_service.py tests/sandbox/test_execution_permissions.py` | 0 | Docker-only execution, explicit approval, one-shot execution, container permissions, and failure paths passed. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 6.1–6.7, 8.1–8.7, 9.7–9.8 | `pytest -q tests/commands/test_sandbox_commands.py tests/sandbox/test_failure_observability.py tests/sandbox/test_execution_artifacts.py` | 0 | Commands, lifecycle events, redaction, status, and artifacts passed. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 7.1–7.6 | `pytest -q tests/test_plan_approval.py tests/test_assistant_lifecycle_hardening.py tests/sandbox/test_approval_repository.py tests/sandbox/test_execution_service.py` | 0 | Retained plan approval, immutable binding, replay rejection, and validated-only synthesis passed. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 9.1 | `DockerRunner real digest-pinned hardened-boundary probe` | 0 | Real Linux Docker execution produced result.json and summary.md with all hardened controls asserted. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 10.1–10.7 | `make lint-vnalpha && make test-vnalpha && make verify-r4 && packaging/scripts/openstock-verify --ci` | 0 | Lint, full suite, R4, and verifier passed. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 10.4 | `PIP_INDEX_URL=https://pypi.org/simple make verify-vnalpha-package` | 0 | Standalone package bundled 31 wheels and passed 55 clean no-index install/eval checks. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:04:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | OpenSpec | `openspec validate prod-b-sandbox-mvp --strict` | 0 | Strict requirement/scenario validation passed. | `openspec/changes/prod-b-sandbox-mvp/evidence/dependency-closure.md` |
| 2026-07-13T01:18:00Z | `5dc6dce` | 10.8 | `gh pr view 62 --json number,state,url,headRefOid` | 0 | Draft dependency-closure PR published with local gate evidence attached. | https://github.com/duvu/openstock/pull/62 |
| 2026-07-13T03:45:31Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 6.1, 7.4–7.6, 9.7, 10.9–10.11 | `pytest -q tests/sandbox/test_generation.py tests/sandbox/test_execution_service.py tests/sandbox/test_execution_permissions.py tests/sandbox/test_approval_repository.py tests/commands/test_sandbox_commands.py tests/test_chat_controller.py tests/test_plan_approval.py` | 0 | 128 tests pass for bounded input-dependent generation, exact slash-command prepared-turn continuation, approval, one-shot execution, and validated-only synthesis. | local command transcript |
| 2026-07-13T03:45:31Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 0.6, 4.1–4.10, 9.1, 9.9, 10.12 | `pytest -q tests/sandbox/test_docker_runtime.py tests/sandbox/test_docker_orchestration.py tests/sandbox/test_docker_orchestration_terminalization.py tests/sandbox/test_execution_artifacts.py tests/sandbox/test_artifact_writer_validation_finalization.py tests/sandbox/test_failure_observability.py` | 0 | 63 tests pass for Docker-only runtime behavior and schema-v2 preflight/effective-security evidence without host paths. | local command transcript |
| 2026-07-13T03:45:31Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 10.10–10.12 | `pytest -q tests/sandbox/test_generation.py tests/sandbox/test_execution_service.py tests/sandbox/test_execution_permissions.py tests/sandbox/test_approval_repository.py tests/sandbox/test_repository.py tests/sandbox/test_repository_quality.py tests/sandbox/test_docker_runtime.py tests/sandbox/test_docker_orchestration.py tests/sandbox/test_docker_orchestration_terminalization.py tests/sandbox/test_execution_artifacts.py tests/sandbox/test_artifact_writer_validation_finalization.py tests/sandbox/test_failure_observability.py tests/commands/test_sandbox_commands.py tests/test_chat_controller.py tests/test_plan_approval.py` | 0 | 238 combined repair and regression tests pass after splitting the execution facade below 250 pure LOC. | local command transcript |
| 2026-07-13T04:05:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 3.4, 9.2–9.4 | `pytest -q tests/sandbox/test_static_guard.py tests/sandbox/test_generation.py` | 0 | 37 tests pass, including keyword write modes and output-path traversal rejection. | local command transcript |
| 2026-07-13T04:05:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | 9.1–9.9, 10.9–10.12 | `pytest -q tests/sandbox tests/commands/test_sandbox_commands.py tests/test_chat_controller.py tests/test_plan_approval.py` with the two outer-seccomp Unix-socket setup cases deselected | 0 | Complete sandbox-focused suite reached 100%; only environment-prohibited AF_UNIX fixture setup was excluded. | local command transcript |
| 2026-07-13T04:05:00Z | `873425d62eb1aea7fc7519b62fde22ac195c7872` + working tree | OpenSpec | `openspec validate prod-b-sandbox-mvp --strict` | 0 | Strict validation passed after the final verifier and guard repairs. | local command transcript |

## Manual surface evidence

| Surface | Command | Result |
|---|---|---|
| CLI help | `vnalpha cmd --help` | Exit 0; command argument and date/help options rendered. |
| CLI happy path | `vnalpha cmd '/sandbox run mean of 1, 2, 3'` | Exit 0; persisted queued job and exact prepared-turn preview with purpose, code digest/summary, limits, image digest, correlation ID, and explicit awaiting-approval message; no CLI execution started. |
| CLI empty path | `vnalpha cmd '/sandbox status missing-job'` | Exit 0; rendered `Sandbox job not found.` inline. |
| CLI invalid path | `vnalpha cmd '/sandbox inspect missing-job'` | Exit 1; rendered the supported subcommands and `CommandValidationError`. |

## PR evidence

Draft PR #62 contains the dependency-closure implementation and evidence:
https://github.com/duvu/openstock/pull/62

## Completion status

Final implementation SHA: pending
OpenSpec verifier result: INCOMPLETE until final-SHA gates pass
Ready to archive: pending
