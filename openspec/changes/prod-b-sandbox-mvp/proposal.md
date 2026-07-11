# Proposal: Sandboxed compute MVP for auto research

## Summary

Add OpenSpec for Phase B of the production/MVP2 OpenStock roadmap:

```text
Phase B: Sandboxed Compute MVP
```

This phase introduces a controlled compute layer that lets the AI workspace generate and run small research calculations, indicator experiments, charts, and validation scripts inside a constrained sandbox.

The system remains inside the read-only research boundary.

## Why

OpenStock should become an opencode-like auto research workspace for Vietnamese equity research. To do that, it needs a safe way to let the assistant perform ad-hoc calculations without giving it unsafe shell, network, broker, account, or trading execution access.

The correct abstraction is not raw shell access. The correct abstraction is:

```text
SandboxJob
  -> policy check
  -> static code guard
  -> isolated execution
  -> output schema validation
  -> artifact persistence
  -> audit/trace evidence
```

This allows the assistant to produce useful research artifacts while remaining safe, reproducible, and reviewable.

## Goals

- Add a first-class `SandboxJob` model for generated research compute.
- Add a sandbox runner that executes Python research code in a constrained environment.
- Disable network access for sandbox jobs.
- Restrict filesystem reads/writes to approved paths.
- Add CPU, memory, and runtime limits.
- Add static guards for dangerous imports and patterns.
- Make static guards defense-in-depth controls, not the execution isolation boundary.
- Require explicit user approval for every generated-code execution.
- Use Docker Engine as the only sandbox runtime on a supported Linux host, rejecting unavailable or unsupported environments without local-process fallback.
- Run each job from an immutable, prebuilt container image with OS-level isolation and explicit container hardening.
- Add artifact persistence for tables, JSON summaries, markdown reports, and charts.
- Add `/sandbox` composer commands.
- Add assistant planning support for sandbox jobs that require approval.
- Preserve read-only research boundary.
- Preserve closed-loop logging.

## Non-goals

- No broker integration.
- No order generation, order placement, order simulation tied to live accounts, or trading execution.
- No account, portfolio, margin, transfer, or allocation tools.
- No unrestricted shell.
- No unrestricted filesystem access.
- No network-enabled sandbox jobs in MVP.
- No persistent long-running workers in this phase unless explicitly bounded by resource policy.

## Scope

### SandboxJob

The implementation SHALL define a `SandboxJob` or equivalent model with at least:

```text
job_id
purpose
input_datasets
generated_code
allowed_imports
resource_limits
network_policy
filesystem_policy
output_schema
expected_artifacts
correlation_id
created_at
status
```

### Sandbox runner

The sandbox runner SHALL execute generated Python in a constrained environment:

```text
runtime: Docker Engine only, on a supported Linux host after preflight
image: immutable prebuilt image referenced by digest; no build, pull, or mutable tag at job execution
network: disabled with --network none
root filesystem: read-only
input mounts: approved data snapshots mounted read-only
write paths: sole writable mount is the job output directory
user: non-root
capabilities: all dropped unless a documented minimum exception is required
pids: bounded
max_runtime_seconds: bounded and enforced by the runner
max_memory_mb: bounded
max_cpu: bounded
```

Docker Engine availability and supported Linux host preflight SHALL be checked before a job is accepted for execution. If Docker is unavailable, the host is unsupported, or preflight fails, the system SHALL reject the job, persist rejection evidence, and SHALL NOT run generated code through a local interpreter or any other fallback runtime. Docker OS isolation is the primary execution boundary. Static guards, policy checks, schema validation, and artifact validation are defense-in-depth controls and do not replace that boundary.

### Static guard

Before execution, generated code SHALL be checked for disallowed imports and dangerous patterns.

Examples of denied behavior:

```text
os.system
subprocess shell execution
socket/network access
requests/httpx/urllib
pip install
env/secret access
filesystem access outside sandbox
broker/order/account/portfolio/margin/trading execution references
```

### Output validation

Sandbox jobs SHALL produce structured output:

```text
result.json
summary.md
artifacts manifest
optional chart files
optional table files
```

The runner SHALL validate output against an expected schema before the assistant synthesizes the final answer.

### Composer command surface

The TUI composer SHALL support:

```text
/sandbox run <purpose>
/sandbox status <job-id>
/sandbox artifact <job-id>
/sandbox list --latest
```

The canonical persisted layout SHALL be `logs/runs/<run-id>/sandbox/<job-id>/`, containing the job request metadata, generated code, input dataset references or snapshots, the job output directory, stdout and stderr capture, guard result, execution result, validation result, artifact manifest, and lifecycle-event evidence. The container SHALL receive only the approved input material as read-only mounts and the canonical job output directory as its sole writable mount. Evidence SHALL identify the image digest, Docker preflight result, effective resource limits, mount policy, network policy, container security controls, generated-code hash, input references, and correlation ID so each result can be reproduced and audited.

Unsupported subcommands SHALL render clear unsupported messages and log lifecycle events.

### Assistant integration

Natural-language requests that require generated code SHALL produce a plan preview and require explicit user approval before every execution. Deterministic, bounded, read-only, or policy-safe characteristics SHALL NOT bypass approval.

## Success criteria

This phase is complete only when:

```text
- SandboxJob model exists.
- Sandbox runner enforces no-network policy.
- Sandbox runner rejects unsupported Linux hosts, unavailable Docker Engine, and failed Docker preflight without local fallback.
- Sandbox runner uses an immutable prebuilt image and Docker OS isolation with a read-only root filesystem, read-only input mounts, and only the job output mount writable.
- Sandbox runner enforces non-root execution, dropped capabilities, PID, CPU, memory, and runtime limits.
- Sandbox runner enforces bounded CPU/memory/runtime policy.
- Sandbox runner restricts writes to the job output directory.
- Static guard rejects dangerous imports and patterns.
- `/sandbox run` creates and executes a policy-approved research job.
- `/sandbox status <job-id>` renders job status inline.
- `/sandbox artifact <job-id>` renders artifact metadata inline.
- Sandbox jobs emit lifecycle events.
- Sandbox failures are captured into errors/logs.
- Output artifacts are reproducible from persisted inputs and generated code.
- Canonical job artifacts include execution, guard, validation, and lifecycle evidence required to audit the container security contract.
- Every generated-code execution has explicit user approval recorded with its job evidence.
- read-only research boundary is preserved.
```

## Validation commands

Run:

```bash
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Additional expected sandbox tests:

```bash
pytest vnalpha/tests -k sandbox
```

## Production boundary

The sandbox is for research computation only.

It may compute indicators, feature prototypes, statistical summaries, offline backtest-like research metrics, charts, and reports.

It SHALL NOT perform or connect to trading execution, live broker systems, account state, portfolio management, margin, transfer, or allocation workflows.
