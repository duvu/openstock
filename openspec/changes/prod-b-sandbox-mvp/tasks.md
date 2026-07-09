# Tasks: Sandboxed compute MVP for auto research

## 0. Governance

- [ ] 0.1 Keep all sandbox behavior inside the read-only research boundary.
- [ ] 0.2 Deny broker/order/account/portfolio/margin/transfer/allocation/trading execution capabilities.
- [ ] 0.3 Do not expose unrestricted shell access.
- [ ] 0.4 Do not allow network access in sandbox MVP.
- [ ] 0.5 Preserve redaction-by-default logging.
- [ ] 0.6 Persist enough evidence to reproduce every sandbox result.

## 1. Sandbox domain model

- [ ] 1.1 Add `SandboxJob` model.
- [ ] 1.2 Add job status enum: `QUEUED`, `VALIDATING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED`, `CANCELLED`.
- [ ] 1.3 Add resource limits model: runtime seconds, memory MB, CPU count.
- [ ] 1.4 Add filesystem policy model: approved read paths and job output write path.
- [ ] 1.5 Add network policy field with MVP default `disabled`.
- [ ] 1.6 Add output schema / expected artifacts model.
- [ ] 1.7 Add correlation ID to every job.

## 2. Persistence and artifact layout

- [ ] 2.1 Add warehouse migration for sandbox jobs if persistence is database-backed.
- [ ] 2.2 Add filesystem artifact layout under `logs/runs/<run-id>/sandbox/<job-id>/` or equivalent.
- [ ] 2.3 Persist generated code as an artifact.
- [ ] 2.4 Persist input dataset references or snapshots.
- [ ] 2.5 Persist `result.json`.
- [ ] 2.6 Persist `summary.md`.
- [ ] 2.7 Persist artifact manifest.
- [ ] 2.8 Persist failure reason and guard rejection reason.

## 3. Static guard

- [ ] 3.1 Add static code guard before execution.
- [ ] 3.2 Deny `os.system` and unsafe shell patterns.
- [ ] 3.3 Deny `subprocess` unless explicitly implemented as an internal runner boundary, not user code.
- [ ] 3.4 Deny network libraries and socket access.
- [ ] 3.5 Deny `pip install` and dynamic dependency installation.
- [ ] 3.6 Deny environment variable and secret access.
- [ ] 3.7 Deny filesystem writes outside the job output directory.
- [ ] 3.8 Deny imports or identifiers related to broker/order/account/portfolio/margin/trading execution.
- [ ] 3.9 Add tests for all deny rules.

## 4. Sandbox runner

- [ ] 4.1 Add sandbox runner service/module.
- [ ] 4.2 Execute generated Python with network disabled.
- [ ] 4.3 Enforce max runtime.
- [ ] 4.4 Enforce max memory.
- [ ] 4.5 Enforce CPU limit.
- [ ] 4.6 Mount approved data paths read-only.
- [ ] 4.7 Mount job output path writeable.
- [ ] 4.8 Capture stdout/stderr into artifacts.
- [ ] 4.9 Return structured execution result.
- [ ] 4.10 Capture exceptions into observability.

## 5. Output validation

- [ ] 5.1 Define required output manifest schema.
- [ ] 5.2 Validate `result.json` schema.
- [ ] 5.3 Validate `summary.md` exists for successful jobs.
- [ ] 5.4 Validate chart/table artifact references if present.
- [ ] 5.5 Mark job failed if expected artifacts are missing.
- [ ] 5.6 Add tests for output validation failure.

## 6. Command surface

- [ ] 6.1 Add `/sandbox run <purpose>` route.
- [ ] 6.2 Add `/sandbox status <job-id>` route.
- [ ] 6.3 Add `/sandbox artifact <job-id>` route.
- [ ] 6.4 Add `/sandbox list --latest` route.
- [ ] 6.5 Render unsupported sandbox subcommands inline.
- [ ] 6.6 Emit command lifecycle events for all sandbox commands.
- [ ] 6.7 Render artifact paths/status in OutputStream.

## 7. Assistant integration

- [ ] 7.1 Extend intent/planning to identify sandbox-required calculations.
- [ ] 7.2 Add `sandbox.run_research_code` or equivalent tool to planner allowlist only if approval-gated.
- [ ] 7.3 Require plan preview before generated code execution.
- [ ] 7.4 Show generated code summary and input dataset list before approval.
- [ ] 7.5 Execute only approved, policy-safe SandboxJob instances.
- [ ] 7.6 Synthesize final answer from validated sandbox outputs only.

## 8. Observability

- [ ] 8.1 Emit `SANDBOX_JOB_CREATED`.
- [ ] 8.2 Emit `SANDBOX_GUARD_REJECTED` when guard fails.
- [ ] 8.3 Emit `SANDBOX_JOB_STARTED`.
- [ ] 8.4 Emit `SANDBOX_JOB_SUCCEEDED`.
- [ ] 8.5 Emit `SANDBOX_JOB_FAILED`.
- [ ] 8.6 Include correlation ID in every sandbox event.
- [ ] 8.7 Preserve redaction-by-default.

## 9. Tests

- [ ] 9.1 Test safe generated calculation succeeds.
- [ ] 9.2 Test network import is rejected.
- [ ] 9.3 Test shell/subprocess pattern is rejected.
- [ ] 9.4 Test write outside output directory is rejected.
- [ ] 9.5 Test broker/order/account/trading references are rejected.
- [ ] 9.6 Test missing output artifact fails validation.
- [ ] 9.7 Test `/sandbox run` lifecycle events.
- [ ] 9.8 Test `/sandbox status` rendering.
- [ ] 9.9 Test artifact manifest persistence.

## 10. Documentation and validation

- [ ] 10.1 Add sandbox architecture docs.
- [ ] 10.2 Document safe/unsafe imports and patterns.
- [ ] 10.3 Document read-only research boundary for sandbox.
- [ ] 10.4 Run `make test-vnalpha`.
- [ ] 10.5 Run `make lint-vnalpha`.
- [ ] 10.6 Run `make verify-r4`.
- [ ] 10.7 Run `openstock-verify --ci`.
- [ ] 10.8 Attach validation evidence to PR.
