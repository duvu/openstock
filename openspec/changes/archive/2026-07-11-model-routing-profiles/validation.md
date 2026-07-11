# Validation: Model routing profiles

## Scope reviewed

The implementation was reviewed against:

```text
openspec/changes/model-routing-profiles/proposal.md
openspec/changes/model-routing-profiles/review.md
openspec/changes/model-routing-profiles/design.md
openspec/changes/model-routing-profiles/specs/model-routing-profiles/spec.md
openspec/changes/model-routing-profiles/tasks.md
```

## Implementation evidence

### Profiles and configuration

```text
vnalpha/src/vnalpha/model_routing/models.py
vnalpha/src/vnalpha/model_routing/config.py
vnalpha/src/vnalpha/model_routing/policy.py
vnalpha/src/vnalpha/model_routing/resolver.py
```

Evidence:

- four named profiles are defined;
- preferred and legacy environment variables are supported;
- fallback chains are configurable and validated;
- routing uses stage, task type, and bounded complexity metadata;
- fallback routes with duplicate resolved model IDs are suppressed.

### Overrides

```text
vnalpha/src/vnalpha/model_routing/overrides.py
vnalpha/src/vnalpha/model_routing/runtime.py
```

Evidence:

- per-call profile has highest resolver precedence;
- session override precedes workspace override;
- workspace override is persisted in `model-routing.json` under the active workspace;
- reset supports session, workspace, and all scopes;
- latest successful route is available to `/model status`.

### Gateway and assistant integration

```text
vnalpha/src/vnalpha/assistant/gateway.py
vnalpha/src/vnalpha/assistant/intent.py
vnalpha/src/vnalpha/assistant/synthesizer.py
vnalpha/src/vnalpha/warehouse/assistant_repo.py
```

Evidence:

- production HTTP payload uses the resolved model ID;
- retryable provider/transport failures can advance through fallback profiles;
- returned usage includes the actual successful route;
- classifier passes `classify/intent_classification` metadata and retries invalid JSON with `default`;
- synthesizer passes plan-derived task and complexity metadata;
- `llm_trace.model` can be updated from routed usage after fallback.

### Commands and workspace compaction

```text
vnalpha/src/vnalpha/commands/handlers/model.py
vnalpha/src/vnalpha/commands/setup.py
vnalpha/src/vnalpha/commands/parser.py
vnalpha/src/vnalpha/workspace_context/compaction.py
vnalpha/src/vnalpha/commands/handlers/context.py
```

Evidence:

- `/model status`, `profiles`, `use`, `reset`, and `explain-route` are registered;
- profile shorthand and `/models` alias are supported;
- invalid profiles/scopes/stages are validation errors;
- deterministic workspace compaction remains the default;
- `/context compact --llm` routes as `compact/workspace_compaction` and falls back to deterministic output on failure.

### Observability

```text
vnalpha/src/vnalpha/model_routing/observability.py
```

Evidence:

- route, call, fallback, and override event families are implemented;
- safe metadata includes route, fallback, latency, usage, and cost fields;
- prompt/content fields are excluded by an allowlist.

### Automated test code added

```text
vnalpha/tests/test_model_routing.py
vnalpha/tests/commands/test_model_commands.py
vnalpha/tests/workspace_context/test_model_routed_compaction.py
```

Coverage includes configuration, policy, overrides, persistence, fallback order, gateway model payload, classifier recovery, model commands, metadata redaction, and routed compaction.

## Validation commands

The following commands are required before the OpenSpec can be marked fully validated:

```text
cd vnalpha && pytest -q tests/test_model_routing.py tests/commands/test_model_commands.py tests/workspace_context/test_model_routed_compaction.py
make test-vnalpha
make lint-vnalpha
make verify-r4
packaging/scripts/openstock-verify --ci
```

### Current execution status

```text
Focused tests:          NOT RUN in the GitHub connector environment
Full test suite:        NOT RUN in the GitHub connector environment
Ruff lint/format:       NOT RUN in the GitHub connector environment
R4 verification:       NOT RUN in the GitHub connector environment
openstock-verify --ci:  NOT RUN in the GitHub connector environment
```

The branch contains implementation and test code, but command-level validation remains intentionally unchecked in `tasks.md` until these commands are executed on a repository checkout with development dependencies.

## Known non-blocking limitation

Detailed TUI model-profile display is provided through `/model status`; the compact status/footer does not continuously display the active profile. This satisfies the proposal's `TUI status or /model status` requirement without adding noise to the main workspace.
