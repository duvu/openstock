# Design: Capability-aware strict-schema fallback

## Decisions

### Primary route remains callable

The primary route is still attempted for compatibility even if no capability is
declared. Existing installations may already use a verified primary alias but
have not yet populated the new capability environment variables. This change
only gates fallback selection.

### Fallback capability is explicit

For a strict JSON Schema request, fallback candidates must explicitly declare
`ModelCapability.JSON_SCHEMA`. Missing configuration means unsupported. Provider
or model names are never used as evidence.

### Preserve deterministic order and duplicate suppression

The configured profile fallback chain remains authoritative. Candidates are
visited in order, but profiles resolving to a model ID already attempted are
skipped. Capability filtering does not reorder routes.

### Typed no-compatible-fallback failure

When the primary strict route fails and no distinct compatible fallback exists,
the gateway raises `LLMNoCompatibleFallbackError` with stable error code
`no_compatible_fallback`. The original primary failure is stored on the error
and set as the Python exception cause.

If compatible fallbacks exist but all attempted routes fail, the existing
route-specific gateway error behavior remains in force.

### One downgrade per route

Each attempted route may downgrade from `json_schema` to `json_object` once only
when the endpoint explicitly rejects strict schema format. This compatibility
attempt is local to that route and does not add transport retry budget.

### One source of truth across code and documentation

The same PR updates:

- routing implementation and typed errors;
- focused and full-suite tests;
- `/model` operator surfaces;
- `.env.example` and package configuration;
- AI-layer documentation;
- required CI focused tests;
- OpenSpec evidence.

No surface may claim a capability or fallback that the runtime does not use.

## Non-goals

- No production alias inventory.
- No capability auto-detection.
- No extra transport retries.
- No deterministic research behavior change.
