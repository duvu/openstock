# Tasks: Sandboxed compute MVP for auto research

## 0. Governance

- [x] 0.1 Keep all sandbox behavior inside the read-only research boundary.
- [x] 0.2 Deny broker/order/account/portfolio/margin/transfer/allocation/trading execution capabilities.
- [x] 0.3 Do not expose unrestricted shell access.
- [x] 0.4 Do not allow network access in sandbox MVP, enforced through Docker `--network none`.
- [x] 0.5 Preserve redaction-by-default logging and record explicit approval for every generated-code execution.
- [x] 0.6 Persist enough canonical evidence to reproduce and audit every sandbox result, including Docker preflight, image digest, effective limits, mount and security policy, generated-code hash, inputs, guard, execution, validation, and lifecycle results.

## 1. Sandbox domain model

- [x] 1.1 Add `SandboxJob` model.
- [x] 1.2 Add job status enum: `QUEUED`, `VALIDATING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED`, `CANCELLED`.
- [x] 1.3 Add resource limits model: runtime seconds, memory MB, CPU count.
- [x] 1.4 Add filesystem policy model: approved read paths and job output write path.
- [x] 1.5 Add network policy field with MVP default `disabled`.
- [x] 1.6 Add output schema / expected artifacts model.
- [x] 1.7 Add correlation ID to every job.

## 2. Persistence and artifact layout

- [x] 2.1 Add warehouse migration for sandbox jobs if persistence is database-backed.
- [x] 2.2 Add canonical filesystem artifact layout under `logs/runs/<run-id>/sandbox/<job-id>/` containing request metadata, generated code, input references or snapshots, sole writable job output, stdout/stderr, guard, execution, validation, manifest, and lifecycle evidence.
- [x] 2.3 Persist generated code as an artifact.
- [x] 2.4 Persist input dataset references or snapshots.
- [x] 2.5 Persist `result.json`.
- [x] 2.6 Persist `summary.md`.
- [x] 2.7 Persist artifact manifest.
- [x] 2.8 Persist failure reason and guard rejection reason.

## 3. Static guard

- [x] 3.1 Add static code guard before execution.
- [x] 3.2 Deny `os.system` and unsafe shell patterns.
- [x] 3.3 Deny `subprocess` unless explicitly implemented as an internal runner boundary, not user code.
- [x] 3.4 Deny network libraries and socket access.
- [x] 3.5 Deny `pip install` and dynamic dependency installation.
- [x] 3.6 Deny environment variable and secret access.
- [x] 3.7 Deny filesystem writes outside the job output directory.
- [x] 3.8 Deny imports or identifiers related to broker/order/account/portfolio/margin/trading execution.
- [x] 3.9 Add tests for all deny rules.

## 4. Sandbox runner

- [x] 4.1 Add a Linux-only Docker Engine sandbox runner service/module that preflights Docker and host support, rejects failures, and has no local or alternate runtime fallback.
- [x] 4.2 Execute generated Python in Docker OS isolation from an immutable prebuilt image selected by digest, with `--network none`, a non-root user, and dropped Linux capabilities except documented minimum exceptions.
- [x] 4.3 Enforce max runtime.
- [x] 4.4 Enforce max memory.
- [x] 4.5 Enforce CPU and PID limits.
- [x] 4.6 Mount approved data paths and the container root filesystem read-only.
- [x] 4.7 Mount only the canonical job output path writeable, as the sole writable mount.
- [x] 4.8 Capture stdout/stderr into artifacts.
- [x] 4.9 Return structured execution result.
- [x] 4.10 Capture exceptions into observability, including Docker preflight and unsupported-runtime rejections.

## 5. Output validation

- [x] 5.1 Define required output manifest schema.
- [x] 5.2 Validate `result.json` schema.
- [x] 5.3 Validate `summary.md` exists for successful jobs.
- [x] 5.4 Validate chart/table artifact references if present.
- [x] 5.5 Mark job failed if expected artifacts are missing.
- [x] 5.6 Add tests for output validation failure.

## 6. Command surface

- [x] 6.1 Add `/sandbox run <purpose>` route.
- [x] 6.2 Add `/sandbox status <job-id>` route.
- [x] 6.3 Add `/sandbox artifact <job-id>` route.
- [x] 6.4 Add `/sandbox list --latest` route.
- [x] 6.5 Render unsupported sandbox subcommands inline.
- [x] 6.6 Emit command lifecycle events for all sandbox commands.
- [x] 6.7 Render artifact paths/status in OutputStream.

## 7. Assistant integration

- [x] 7.1 Correct static guard analysis to parse and compile complete Python modules without execution, retaining all deny rules.
- [x] 7.2 Add immutable sandbox approval persistence bound to job ID, plan digest, generated-code digest, approved input references, correlation ID, approver, and timestamp.
- [x] 7.3 Extend intent/planning to identify sandbox-required calculations and create a non-autonomous `sandbox.run_research_code` plan step.
- [x] 7.4 Preview purpose, generated-code summary and digest, input dataset list, limits, and image digest; require explicit approval in every chat mode.
- [x] 7.5 Add one Docker-only sandbox execution service that verifies the exact approval binding and executes only the retained approved SandboxJob after preflight.
- [x] 7.6 Synthesize final answer from validated sandbox outputs only.

## 8. Observability

- [x] 8.1 Emit `SANDBOX_JOB_CREATED`.
- [x] 8.2 Emit `SANDBOX_GUARD_REJECTED` when guard fails.
- [x] 8.3 Emit `SANDBOX_JOB_STARTED`.
- [x] 8.4 Emit `SANDBOX_JOB_SUCCEEDED`.
- [x] 8.5 Emit `SANDBOX_JOB_FAILED`.
- [x] 8.6 Include correlation ID in every sandbox event.
- [x] 8.7 Preserve redaction-by-default.

## 9. Tests

- [x] 9.1 Test safe generated calculation succeeds only after explicit approval in the hardened Docker runtime.
- [x] 9.2 Test network import is rejected.
- [x] 9.3 Test shell/subprocess pattern is rejected.
- [x] 9.4 Test write outside output directory is rejected.
- [x] 9.5 Test broker/order/account/trading references are rejected.
- [x] 9.6 Test missing output artifact fails validation and canonical evidence is persisted.
- [x] 9.7 Test `/sandbox run` lifecycle events.
- [x] 9.8 Test `/sandbox status` rendering.
- [x] 9.9 Test artifact manifest and canonical container-security evidence persistence.

## 10. Documentation and validation

- [x] 10.1 Add sandbox architecture docs.
- [x] 10.2 Document safe/unsafe imports and patterns as defense-in-depth controls.
- [x] 10.3 Document the read-only research boundary, Linux-only Docker contract, approval gate, and no-fallback behavior for sandbox.
- [ ] 10.4 Run `make test-vnalpha` on the exact final implementation SHA.
- [ ] 10.5 Run `make lint-vnalpha` on the exact final implementation SHA.
- [ ] 10.6 Run `make verify-r4` on the exact final implementation SHA.
- [ ] 10.7 Run `openstock-verify --ci` on the exact final implementation SHA.
- [ ] 10.8 Attach final-SHA validation evidence to PR.
- [x] 10.9 Prove `/sandbox run` creates the exact prepared turn and the TUI approval path consumes it without CLI auto-execution.
- [x] 10.10 Replace fixed-success placeholder generation with bounded input-dependent numeric research and fail closed for unsupported prose.
- [x] 10.11 Atomically claim queued jobs before guard or Docker execution and reject replay.
- [x] 10.12 Persist structured Docker preflight and effective security controls without host paths.
- [ ] 10.13 Record one exact final implementation SHA and pass the completion verifier against it.
