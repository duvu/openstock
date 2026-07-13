# Sandboxed Compute

Sandboxed compute is an offline, read-only research capability for small generated
calculations and reports. It is not a shell, a data-fetching mechanism, or a
trading interface.

The built-in generator supports a closed numeric-literal grammar: `mean`,
`median`, `sum`, `minimum`, `maximum`, `range`, and population standard
deviation. For example, `/sandbox run mean of 1, 2, 3` prepares code whose
result depends on those exact values. Unsupported or unbounded prose fails
before a job or artifact is created. Application integrations may inject a
separately governed generator with explicit approved input references.

## Safety boundary

- No broker, order, account, portfolio, margin, transfer, allocation, or trading-execution behavior.
- Docker Engine on a supported Linux host is the only runtime; there is no local interpreter or alternate-runtime fallback.
- The container runs from an immutable prebuilt image digest, with `--network none`, a read-only root filesystem, non-root user, dropped capabilities, CPU/memory/PID/runtime limits, read-only inputs, and one writable job-output mount.
- Generated code is guarded before execution. The guard permits only the prebuilt modules `math`, `statistics`, `json`, `csv`, `datetime`, `collections`, `numpy`, `pandas`, and `matplotlib`; it rejects network, shell, dynamic-execution, off-output-write, and trading-boundary patterns.

## Approval and evidence

Every generated-code execution requires explicit approval. The approval is bound to
the exact job ID, plan digest, generated-code digest, input-reference digest and
list, correlation ID, approver, and timestamp. Replanning, regenerated code, or
changed inputs invalidate that approval.

In the TUI, `/sandbox run <purpose>` creates and persists the exact immutable
prepared turn, renders its preview, and places that same object in the normal
approval slot. Approving consumes the queued job atomically before guard or
Docker work begins, so concurrent replay cannot execute the job twice. The
one-shot CLI remains preview-only because it has no interactive approval
controller.

Canonical evidence is stored under:

```text
logs/runs/<run-id>/sandbox/<job-id>/
```

It includes the request, generated code, input references, guard decision,
execution/validation evidence, manifest, streams, and lifecycle records. Final
assistant synthesis may use validated `result.json`, `summary.md`, and manifest
evidence only.

Execution evidence schema v2 records both failed and successful Docker
preflight and the effective digest, resource/PID limits, mount modes and input
count, network isolation, non-root UID, capability drop, no-new-privileges,
pull policy, and environment-forwarding state. Host paths are not persisted in
that security projection.

## Deployment requirement

Set `VNALPHA_SANDBOX_IMAGE` to an image referenced by a full digest:

```text
registry.example/openstock/vnalpha-sandbox@sha256:<64-lowercase-hex-digest>
```

The image must be built, published, and available to the supported Linux Docker
Engine before any job can run. A missing, mutable, invalid, unavailable, or
preflight-failing image rejects the job without executing generated code.
