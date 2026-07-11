# Tasks: Sandboxed compute MVP for auto research

## 0. Governance

- [ ] 0.1 Keep all sandbox behavior inside the read-only research boundary.
- [ ] 0.2 Deny broker/order/account/portfolio/margin/transfer/allocation/trading execution capabilities.
- [ ] 0.3 Do not expose unrestricted shell access.
- [ ] 0.4 Do not allow network access in sandbox MVP, enforced through Docker `--network none`.
- [ ] 0.5 Preserve redaction-by-default logging and record explicit approval for every generated-code execution.
- [ ] 0.6 Persist enough canonical evidence to reproduce and audit every sandbox result, including Docker preflight, image digest, effective limits, mount and security policy, generated-code hash, inputs, guard, execution, validation, and lifecycle results.

## 1. Sandbox domain model

- [x] 1.1 Add `SandboxJob` model.
- [x] 1.2 Add job status enum: `QUEUED`, `VALIDATING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED`, `CANCELLED`.
- [x] 1.3 Add resource limits model: runtime seconds, memory MB, CPU count.
- [ ] 1.4 Add filesystem policy model: approved read paths and job output write path.
- [x] 1.5 Add network policy field with MVP default `disabled`.
- [ ] 1.6 Add output schema / expected artifacts model.
- [x] 1.7 Add correlation ID to every job.

## 2. Persistence and artifact layout

- [x] 2.1 Add warehouse migration for sandbox jobs if persistence is database-backed.
- [ ] 2.2 Add canonical filesystem artifact layout under `logs/runs/<run-id>/sandbox/<job-id>/` containing request metadata, generated code, input references or snapshots, sole writable job output, stdout/stderr, guard, execution, validation, manifest, and lifecycle evidence.
- [ ] 2.3 Persist generated code as an artifact.
- [x] 2.4 Persist input dataset references or snapshots.
- [ ] 2.5 Persist `result.json`.
- [ ] 2.6 Persist `summary.md`.
- [ ] 2.7 Persist artifact manifest.
- [x] 2.8 Persist failure reason and guard rejection reason.

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

- [ ] 4.1 Add a Linux-only Docker Engine sandbox runner service/module that preflights Docker and host support, rejects failures, and has no local or alternate runtime fallback.
- [ ] 4.2 Execute generated Python in Docker OS isolation from an immutable prebuilt image selected by digest, with `--network none`, a non-root user, and dropped Linux capabilities except documented minimum exceptions.
- [ ] 4.3 Enforce max runtime.
- [ ] 4.4 Enforce max memory.
- [ ] 4.5 Enforce CPU and PID limits.
- [ ] 4.6 Mount approved data paths and the container root filesystem read-only.
- [ ] 4.7 Mount only the canonical job output path writeable, as the sole writable mount.
- [ ] 4.8 Capture stdout/stderr into artifacts.
- [ ] 4.9 Return structured execution result.
- [ ] 4.10 Capture exceptions into observability, including Docker preflight and unsupported-runtime rejections.

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
- [ ] 7.2 Add `sandbox.run_research_code` or equivalent tool to planner allowlist only if every execution is explicit-approval-gated, with no deterministic or policy-safe exception.
- [ ] 7.3 Require plan preview and explicit approval before every generated-code execution.
- [ ] 7.4 Show generated code summary and input dataset list before approval.
- [ ] 7.5 Execute only explicitly approved, policy-safe SandboxJob instances after Docker/Linux preflight succeeds.
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

- [ ] 9.1 Test safe generated calculation succeeds only after explicit approval in the hardened Docker runtime.
- [ ] 9.2 Test network import is rejected.
- [ ] 9.3 Test shell/subprocess pattern is rejected.
- [ ] 9.4 Test write outside output directory is rejected.
- [ ] 9.5 Test broker/order/account/trading references are rejected.
- [ ] 9.6 Test missing output artifact fails validation and canonical evidence is persisted.
- [ ] 9.7 Test `/sandbox run` lifecycle events.
- [ ] 9.8 Test `/sandbox status` rendering.
- [ ] 9.9 Test artifact manifest and canonical container-security evidence persistence.

## 10. Documentation and validation

- [ ] 10.1 Add sandbox architecture docs.
- [ ] 10.2 Document safe/unsafe imports and patterns as defense-in-depth controls.
- [ ] 10.3 Document the read-only research boundary, Linux-only Docker contract, approval gate, and no-fallback behavior for sandbox.
- [ ] 10.4 Run `make test-vnalpha`.
- [ ] 10.5 Run `make lint-vnalpha`.
- [ ] 10.6 Run `make verify-r4`.
- [ ] 10.7 Run `openstock-verify --ci`.
- [ ] 10.8 Attach validation evidence to PR.
