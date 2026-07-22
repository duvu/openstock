## Context

Managed assistant execution currently treats synthesis and all post-synthesis
persistence as one failure domain. Tool output is authoritative for read-only
research, yet a gateway, parser, policy, groundedness, audit, projection, or
session-finalization exception can discard it. CLI and TUI then receive only a
generic error without a stable lifecycle stage or correlation evidence.

## Goals / Non-Goals

**Goals:**

- Deliver validated deterministic output whenever a safe read-only plan has
  completed with renderable tool evidence.
- Keep synthesis optional and make later audit/projection/session work
  independently degradable after an answer exists.
- Expose one sanitized diagnostic contract through every assistant surface.

**Non-Goals:**

- Do not recover unsafe writes, approval-required execution, tool failures, or
  turns without a deterministic answer.
- Do not expose prompts, raw model output, provider payloads, credentials, or
  unrestricted exception details.
- Do not alter model routing, tool allowlists, or the research-only boundary.

## Decisions

### Deterministic answer is built before optional synthesis

The execution owner will build one generic deterministic answer from bounded
tool summaries, data, warnings, and source references immediately after safe
tool execution. This avoids relying on intent-specific LLM templates and makes
the authoritative evidence available to later fallback paths.

Alternative: invoke the deterministic renderer only inside each synthesis
exception branch. Rejected because input validation and persistence failures
would still require duplicated, incomplete recovery paths.

### Lifecycle outcomes use typed stages and degraded status

One finite stage model covers synthesis call, parsing, answer validation, audit
persistence, knowledge projection, and session finalization. A usable answer
returns `DEGRADED_SUCCESS` with bounded diagnostic metadata; no usable answer
retains the existing fail-closed failure outcome. Stage/category mapping is
owned by the execution boundary, not by CLI or TUI adapters.

Alternative: map exception class names directly in every surface. Rejected
because class names are unstable and leak implementation details.

### Post-answer persistence has independent best-effort boundaries

The LLM trace, audit, projection, assistant session, and prepared turn each
record truthful terminal state where possible. Failure in optional evidence
projection does not revoke an already validated answer. Required failure
evidence is sanitized and linked by correlation ID.

Alternative: retain one transaction for atomicity. Rejected because a valid
answer is user-visible evidence and must not be hidden by optional persistence.

### Presentation consumes answer metadata

CLI and TUI render the same bounded warning from structured answer metadata,
including stage, stable category, and correlation ID. They do not inspect raw
exceptions or construct diagnostic strings independently.

## Risks / Trade-offs

- [Fallback renderer has insufficient evidence] → Validate the deterministic
  answer before returning it; retain fail-closed status when validation fails.
- [Persistence degradation leaves partial audit rows] → Store truthful status
  per operation and never claim full success after a failed optional stage.
- [Diagnostics reveal internals] → Use stable categories plus the existing
  sanitizer and bounded public projections.
- [Legacy callers bypass the shared execution owner] → Trace managed and
  connected execution paths to one presentation metadata contract and cover
  both CLI and TUI through the shared application surface.

## Migration Plan

1. Add additive answer metadata and typed lifecycle outcomes.
2. Route existing managed and connected execution through the new boundary.
3. Update CLI/TUI rendering to consume additive metadata.
4. Roll back by reverting the additive fallback and presentation path; existing
   success and fail-closed behavior remain valid.
