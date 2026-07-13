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

## Manual surface evidence

| Surface | Command | Result |
|---|---|---|
| CLI help | `vnalpha cmd --help` | Exit 0; command argument and date/help options rendered. |
| CLI happy path | `vnalpha cmd '/sandbox run compare FPT and VNINDEX returns'` | Exit 0; persisted queued job preview with purpose, code digest/summary, limits, image digest, correlation ID, and explicit awaiting-approval message; no execution started. |
| CLI empty path | `vnalpha cmd '/sandbox status missing-job'` | Exit 0; rendered `Sandbox job not found.` inline. |
| CLI invalid path | `vnalpha cmd '/sandbox inspect missing-job'` | Exit 1; rendered the supported subcommands and `CommandValidationError`. |

## PR evidence

Pending publication of the final implementation SHA. Historical PR #58 is merged
and does not contain the current dependency-closure worktree.
