# Design: Sandboxed Compute MVP

## Approval-bound execution

Generated Python is never executable merely because it is deterministic, bounded,
or read-only. A sandbox request becomes executable only through this immutable
sequence:

```text
classify sandbox calculation
  -> construct SandboxJob and preview
  -> persist SandboxApproval bound to job ID, code digest, input references, and plan digest
  -> validate the exact approved binding
  -> guard, Docker preflight, Docker execution, output validation
  -> synthesize from validated artifacts only
```

The approval record is append-only evidence containing the sandbox job ID, plan
digest, generated-code digest, approved input-reference digest and list,
correlation ID, approver, and timestamp. Approval executes the retained immutable
job. It SHALL NOT reclassify, regenerate code, replan, or substitute inputs.

## Planning and policy

The assistant recognizes requests requiring generated research calculations and
builds one `sandbox.run_research_code` plan step. The tool is allowlisted for
assistant planning but is never autonomous or policy-safe for auto-execution.
Every chat mode presents a preview that includes the purpose, code summary,
code digest, input datasets, resource limits, and image digest, then waits for
approval.

The command `/sandbox run <purpose>` follows the same approval path. It does not
provide raw code submission, raw shell access, or an approval bypass.

## Execution service

One application service owns the production composition of repository, artifact
storage/writer, static guard, Docker preflight/runtime, output validator, and
terminalization. Command and chat surfaces call this service; they do not create
local-process fallbacks or independently assemble execution boundaries.

Before execution the service verifies that the persisted approval exactly matches
the retained SandboxJob. It persists request and approval evidence, evaluates and
persists the guard result, then invokes the existing Docker-only orchestrator.
Docker preflight or runtime failure is a terminal, persisted failure or rejection.

## Static guard

The static guard parses and compiles generated source as a Python module
(`ast.parse(..., mode="exec")`). It remains non-executing. Deny rules continue to
inspect the full AST, and all other Docker policy remains the execution boundary.
Allowed imports are limited to `math`, `statistics`, `json`, `csv`, `datetime`,
`collections`, `numpy`, `pandas`, and `matplotlib` (including their submodules).
All other imports are rejected. The guard permits assignments, expressions, and
calls needed for offline analysis, while Docker filesystem mounts remain the
authoritative write boundary.

## Output and synthesis

The service returns an explicit validated-artifact result containing only the
validated `result.json`, `summary.md`, and manifest metadata. Assistant synthesis
for sandbox work receives only this result. It SHALL NOT consume generated code,
stdout, stderr, unvalidated files, or model prose as authoritative sandbox output.

## Observability

Sandbox lifecycle records use fixed, redacted summaries and allowlisted metadata.
They carry the SandboxJob correlation ID and never include generated code, input
paths, stdout, stderr, secrets, or exception messages. The lifecycle covers job
creation, guard rejection, runner start, successful completion, and terminal
failure.

## Testing

Tests prove module-mode safe Python can pass the guard; every sandbox plan waits
for explicit approval even in auto mode; approval cannot be reused after a job,
code, plan, or input change; Docker is the sole runtime; and synthesis rejects
unvalidated output.
