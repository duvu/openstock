# Model routing profiles

OpenStock routes each LLM call through a named model profile instead of embedding provider-specific model IDs in assistant business logic.

## Profiles

| Profile | Intended workload |
|---|---|
| `small` | Intent classification, short titles, constrained lightweight tasks |
| `default` | Normal grounded assistant synthesis and small summaries |
| `reasoning` | Multi-symbol comparison, deep analysis, shortlist reasoning, scenarios, diagnosis |
| `long_context` | Large workspace compaction and long artifact synthesis |

A profile is a policy name. The resolved model ID is configured through environment variables.

## Configuration

Preferred environment variables:

```bash
VNALPHA_MODEL_SMALL=provider/small-model
VNALPHA_MODEL_DEFAULT=provider/default-model
VNALPHA_MODEL_REASONING=provider/reasoning-model
VNALPHA_MODEL_LONG_CONTEXT=provider/long-context-model
```

Backward-compatible aliases are also supported:

```bash
VNALPHA_LLM_MODEL=provider/default-model
VNALPHA_LLM_MODEL_SMALL=provider/small-model
VNALPHA_LLM_MODEL_REASONING=provider/reasoning-model
VNALPHA_LLM_MODEL_LONG_CONTEXT=provider/long-context-model
```

When a profile-specific value is absent, it resolves to the configured default. `long_context` falls back to the reasoning model ID when it is not explicitly configured.

### Fallback chains

Defaults:

```text
small        -> default
default      -> small
reasoning    -> default -> small
long_context -> reasoning -> default
```

Override a chain with comma-separated profile names:

```bash
VNALPHA_MODEL_FALLBACK_REASONING=default,small
VNALPHA_MODEL_FALLBACK_LONG_CONTEXT=reasoning,default
```

Fallbacks with the same resolved model ID are skipped, preventing duplicate calls when all profiles use one model.

Raw arbitrary model-ID overrides are disabled by default. The supported override surface accepts configured profile names only.

## Deterministic routing matrix

| Stage/task | Profile |
|---|---|
| `classify` / `intent_classification` | `small` |
| `title` / `title_generation` | `small` |
| normal answer synthesis | `default` |
| small watchlist summary | `default` |
| large watchlist summary | `reasoning` |
| multi-symbol comparison | `reasoning` |
| deep symbol analysis | `reasoning` |
| shortlist generation | `reasoning` |
| research scenario | `reasoning` |
| diagnosis | `reasoning` |
| workspace compaction | explicit `long_context`, otherwise `reasoning` |

Complexity metadata such as symbol count, artifact count, context size, and `requires_deep_reasoning` may promote a task to the reasoning profile.

The deterministic planner does not call an LLM. If an LLM planner is introduced later, its default profile is `reasoning`.

## Override precedence

```text
1. Explicit per-call profile
2. Session override
3. Workspace override
4. Stage/task policy
5. Configured default profile
```

Session overrides are process-local. Workspace overrides are stored in the active workspace as `model-routing.json` and are loaded by subsequent gateway calls.

## Commands

```text
/model status
/model profiles
/model use small
/model use reasoning --scope session
/model use default --scope workspace
/model reset
/model reset --scope session
/model explain-route classify
/model explain-route deep_symbol_analysis
/model explain-route watchlist_summary --stage synthesize
```

`/model status` shows the active override, resolved model IDs, fallback policy, and the most recent route decision.

`/model use <profile>` defaults to workspace scope. Use `--scope session` for a temporary process-local override.

`/model reset` clears session and workspace overrides by default.

## Gateway behavior

For every call, the gateway:

1. resolves the route;
2. sends the resolved `model_id` in the HTTP payload;
3. retries retryable transport/provider failures for that model;
4. advances through the configured fallback chain;
5. returns usage metadata containing the actual successful route.

The returned usage mapping includes:

```json
{
  "model_route": {
    "profile": "default",
    "model_id": "provider/default-model",
    "stage": "synthesize",
    "task_type": "normal_answer",
    "route_reason": "stage_task_policy"
  }
}
```

Authentication and non-retryable authorization failures do not silently fall back.

## Classifier schema recovery

Intent classification normally routes to `small`. If the response is not valid classifier JSON, the classifier retries once with an explicit `default` profile. The retry is visible in model-route observability.

## Workspace compaction

Deterministic compaction remains the safe default. Callers may pass an LLM client to `compact_workspace`, or use:

```text
/context compact --llm
```

That path routes as `compact/workspace_compaction`, using an explicitly configured `long_context` profile or `reasoning` otherwise. If the LLM path fails, deterministic compaction is used and the result contains a warning.

## Observability

Best-effort audit events:

```text
MODEL_ROUTE_SELECTED
MODEL_CALL_STARTED
MODEL_CALL_SUCCEEDED
MODEL_CALL_FAILED
MODEL_FALLBACK_USED
MODEL_OVERRIDE_SET
MODEL_OVERRIDE_CLEARED
```

Events include stage, task type, profile, model ID, provider, route reason, override source, fallback information, latency, token usage, and estimated cost when supplied by the provider. Prompt and response content are not written to model-route events.

## Recommended operational setup

A cost-conscious local setup can point `small` and `default` at the same low-latency model while reserving a stronger model for `reasoning`. A single-model installation remains supported: duplicate fallback model IDs are skipped automatically.
