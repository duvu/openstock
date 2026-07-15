## Why

Issue #144 is an immediate correctness repair after PR #146 introduced typed
model capabilities without wiring them into route decisions or strict-schema
fallback execution. The repository currently advertises capability-aware model
routing while strict requests still use only the primary route.

## What Changes

- Populate every `ModelRouteDecision` with the capabilities declared for its
  logical profile.
- Filter strict-schema fallback routes to distinct profiles that explicitly
  declare `json_schema` support.
- Preserve configured fallback order and duplicate-model suppression.
- Raise a typed `no_compatible_fallback` error when the primary strict route
  fails and no verified compatible fallback exists.
- Expose capabilities and effective strict-schema fallbacks through `/model`
  status, profiles and route explanation surfaces.
- Keep the existing one-time per-route `json_schema` to `json_object`
  compatibility downgrade and transport retry budget unchanged.
- Update configuration templates, AI-layer documentation and required CI tests
  with the runtime change.

## Capabilities

### Modified Capabilities

- `llm-model-routing`: explicit profile capabilities, strict-compatible fallback
  selection, typed failure and truthful operator status.

## Impact

- Affects only optional assistant model routing; deterministic research remains
  available when the assistant is disabled.
- Does not infer capabilities from model/provider names.
- Does not add transport retries, schema downgrade attempts or unsafe raw-model
  overrides.
