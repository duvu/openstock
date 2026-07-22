## Context

Managed assistant execution treats synthesis and post-synthesis persistence as one
failure domain. Tool output is authoritative for read-only research, yet a gateway,
parser, policy, groundedness, audit, projection, or finalization exception can discard
it. CLI and TUI then receive one generic error without stable correlation evidence.

## Goals / Non-Goals

**Goals:**

- Deliver validated deterministic output whenever a safe read-only plan completed
  with renderable tool evidence.
- Make synthesis, audit, projection, and finalization independently degradable after
  an answer exists.
- Expose one sanitized diagnostic contract through every assistant surface.

**Non-Goals:**

- Do not recover unsafe writes, approval-required execution, tool failures, or turns
  without a deterministic answer.
- Do not expose prompts, raw model output, provider payloads, credentials, or raw
  exception details.

## Decisions

### Deterministic rendering precedes optional synthesis

The execution owner builds one generic deterministic answer from bounded tool
summaries, data, warnings, and source references after safe tool execution. This
keeps authoritative evidence available to all later fallback paths.

### Finite lifecycle diagnostics

A finite stage model covers synthesis call, parse, validation, audit, projection, and
session finalization. A usable answer returns `DEGRADED_SUCCESS`; no usable answer
retains fail-closed behavior. Execution owns stage/category mapping, not UI adapters.

### Post-answer persistence is independently degradable

Trace, audit, projection, assistant session, and prepared turn record truthful status
where possible. An optional persistence failure does not revoke a validated answer.

### Presentation consumes structured metadata

CLI and TUI render the same bounded warning from answer metadata. They never inspect
raw exceptions or construct diagnostics independently.

## Risks / Trade-offs

- [Fallback renderer has insufficient evidence] → Validate before returning and fail
  closed when it cannot validate.
- [Partial audit rows] → Persist truthful terminal status per operation.
- [Diagnostic leakage] → Use stable categories and the shared sanitizer.
