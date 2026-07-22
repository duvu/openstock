## Why

A successful read-only research tool can currently be hidden by a later synthesis,
audit, projection, or session-finalization failure. That violates the evidence-first
assistant contract and leaves CLI/TUI users with one generic error that cannot be
correlated to the failed lifecycle stage.

## What Changes

- Make a deterministic rendering of successful read-only tool outputs the minimum
  deliverable before optional LLM synthesis.
- Return a valid deterministic answer with a bounded warning when synthesis,
  answer validation, audit persistence, knowledge projection, or session
  finalization fails after a usable answer exists.
- Record a stable failure stage, sanitized category, correlation ID, build SHA,
  model route, and trace ID in answer metadata and the CLI/TUI diagnostic surface.
- Preserve fail-closed behavior for unsafe write/execution plans and turns with
  no deterministic answer.

## Capabilities

### New Capabilities

- `assistant-failure-observability`: expose stable, sanitized downstream failure
  diagnostics and correlation evidence consistently through CLI and TUI.

### Modified Capabilities

- `natural-language-research-assistant`: successful read-only tool output remains
  deliverable when optional synthesis or downstream persistence fails.
- `assistant-research-intelligence-tools`: audit and knowledge-projection failures
  degrade an already valid answer instead of suppressing it.

## Impact

- Affects managed assistant execution, deterministic answer rendering, session and
  trace lifecycle persistence, and shared CLI/TUI answer presentation.
- Does not add network access, arbitrary tool execution, broker behavior, trading
  actions, or raw exception exposure.
- Existing successful answers remain compatible; degraded answers gain additive
  metadata and a bounded visible warning.
