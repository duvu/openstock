# Design: Model routing profiles

## Design objective

Add a first-class model routing layer so each LLM call uses a model profile appropriate for the task.

The routing layer must be:

```text
explicit
deterministic
configurable
testable
observable
overridable
safe by default
```

## Architecture overview

Add package:

```text
vnalpha/src/vnalpha/model_routing/
├── __init__.py
├── models.py
├── config.py
├── policy.py
├── resolver.py
├── overrides.py
├── observability.py
└── integration.py
```

Integrate with:

```text
vnalpha.assistant.gateway
vnalpha.assistant.intent
vnalpha.assistant.synthesizer
workspace compaction if implemented
TUI status/footer
commands executor
```

## Core model

### ModelProfile

```python
class ModelProfile(str, Enum):
    SMALL = "small"
    DEFAULT = "default"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"
```

### ModelRouteStage

```python
class ModelRouteStage(str, Enum):
    CLASSIFY = "classify"
    PLAN = "plan"
    SYNTHESIZE = "synthesize"
    COMPACT = "compact"
    TITLE = "title"
    DIAGNOSE = "diagnose"
    GENERIC = "generic"
```

### ModelTaskType

```text
intent_classification
normal_answer
simple_summary
watchlist_summary
deep_symbol_analysis
shortlist_generation
research_scenario
workspace_compaction
error_diagnosis
title_generation
```

### ModelRouteDecision

```python
@dataclass
class ModelRouteDecision:
    profile: ModelProfile
    model_id: str
    provider: str | None
    stage: str
    task_type: str | None
    route_reason: str
    override_source: str | None
    fallback_chain: list[str]
```

## Configuration

Add config file support where project config currently lives. If no central config exists, support env-first MVP.

Suggested env variables:

```text
VNALPHA_MODEL_SMALL
VNALPHA_MODEL_DEFAULT
VNALPHA_MODEL_REASONING
VNALPHA_MODEL_LONG_CONTEXT
VNALPHA_MODEL_FALLBACK_DEFAULT
VNALPHA_MODEL_ALLOW_RAW_OVERRIDE=false
```

Suggested config structure:

```yaml
model_profiles:
  small: openrouter/provider-small
  default: openrouter/provider-default
  reasoning: openrouter/provider-reasoning
  long_context: openrouter/provider-long-context
fallbacks:
  reasoning: [default, small]
  default: [small]
  long_context: [reasoning, default]
routing:
  classify: small
  synthesize: default
  compact: long_context
  diagnose: reasoning
```

The code must validate:

```text
required profiles exist
profile names are valid
fallback profiles exist
raw model id override disabled by default
```

## Routing policy

`ModelRoutingPolicy.select_profile(stage, task_type, metadata)` should implement deterministic rules.

Default matrix:

```text
stage=classify                                      -> small
stage=title                                         -> small
stage=synthesize, task=normal_answer                -> default
stage=synthesize, task=simple_summary               -> default
stage=synthesize, task=watchlist_summary, small set  -> default
stage=synthesize, task=watchlist_summary, large set  -> reasoning
stage=synthesize, task=deep_symbol_analysis          -> reasoning
stage=synthesize, task=shortlist_generation          -> reasoning
stage=synthesize, task=research_scenario             -> reasoning
stage=compact                                        -> long_context if configured else reasoning
stage=diagnose                                       -> reasoning
unknown                                              -> default
```

Complexity metadata may include:

```text
symbol_count
artifact_count
context_bytes
requires_deep_reasoning
requires_json_schema
latency_preference
cost_preference
```

## Override policy

Override precedence:

```text
1. explicit per-call override
2. session/workspace override from /model use
3. task/stage routing policy
4. configured default profile
5. safe hard fallback profile
```

Override sources:

```text
per_call
session
workspace
env
none
```

Implement:

```text
ModelOverrideStore
- get_current_override()
- set_override(profile)
- clear_override()
```

Initial MVP may store override in memory/session. If workspace_context exists, store it in workspace state.

## Gateway integration

Current LLM calls should accept stage and optional route metadata.

Suggested gateway API:

```python
chat(messages, *, stage: str, task_type: str | None = None, model_profile: str | None = None, route_metadata: dict | None = None)
```

Flow:

```text
caller passes stage/task metadata
gateway asks ModelRouter for route decision
gateway sends resolved model_id to underlying LLM service
gateway logs route and usage
gateway applies fallback if call fails
```

Do not require business logic to know actual provider/model ids.

## Assistant integration

### Intent classifier

Use:

```text
stage=classify
task_type=intent_classification
profile=small
```

If JSON parse/validation fails, retry once with `default` profile.

### Planner

Deterministic planner should not call LLM. No model route needed.

If future LLM planning is added, use `reasoning` by default.

### Synthesizer

Pass task type from plan intent:

```text
explain_symbol -> normal_answer or deep_symbol_analysis if deep workflow
compare_symbols -> reasoning if multiple symbols or complex caveats
summarize_watchlist -> default/reasoning depending size
generate_shortlist -> reasoning
research_scenario -> reasoning
```

### Workspace compaction

Use:

```text
stage=compact
task_type=workspace_compaction
profile=long_context if configured, else reasoning
```

## Commands

Add command handler:

```text
vnalpha/src/vnalpha/commands/handlers/model.py
```

Commands:

```text
/model status
/model profiles
/model use <profile>
/model reset
/model explain-route <stage-or-task>
```

Behavior:

### `/model status`

Show:

```text
active override
configured profiles
current default profile
fallback policy
last route decision if available
```

### `/model profiles`

Show available configured profile names and resolved model ids. Redact provider secrets if any.

### `/model use <profile>`

Set session/workspace override.

Only allow configured profile names:

```text
small
default
reasoning
long_context
```

### `/model reset`

Clear override and return to routing policy.

### `/model explain-route <stage-or-task>`

Return the route decision that would be used for a given stage/task.

## TUI integration

Status/footer should compactly show:

```text
model=default
model=reasoning override
model=small classify
```

Do not overload the UI. Detailed model config belongs in `/model status`.

## Observability

Add events:

```text
MODEL_ROUTE_SELECTED
MODEL_CALL_STARTED
MODEL_CALL_SUCCEEDED
MODEL_CALL_FAILED
MODEL_FALLBACK_USED
MODEL_OVERRIDE_SET
MODEL_OVERRIDE_CLEARED
```

Metadata:

```text
stage
task_type
profile
model_id
provider
route_reason
override_source
fallback_from
fallback_to
latency_ms
tokens_in
tokens_out
estimated_cost
correlation_id
```

Avoid logging prompt content in model route events.

## Fallback design

Fallback chain comes from config.

Example:

```text
reasoning -> default -> small
long_context -> reasoning -> default
```

Fallback should trigger on:

```text
transport error
provider timeout
rate limit when retryable
model unavailable
invalid model id
```

Fallback should not hide schema/validation failures silently. For JSON-required tasks, fallback may retry with a stronger profile if small/default output fails validation.

## Tests

Required tests:

```text
config loads env profiles
config validates missing profiles
policy routes classify to small
policy routes normal synthesis to default
policy routes deep analysis to reasoning
policy routes compact to long_context or reasoning
session override wins over policy
per-call override wins over session override
reset clears override
fallback chain resolves
MODEL_ROUTE_SELECTED event emitted
/model status works
/model use small works
/model reset works
gateway passes selected model_id
classifier retries default after invalid small JSON
```

## Documentation

Add:

```text
vnalpha/docs/model-routing-profiles.md
```

Update TUI docs if status/footer displays model profile.

Document:

```text
profiles
configuration
routing matrix
override commands
fallback behavior
observability
recommended model classes
```

## Validation

Implementation PR should run:

```text
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
```

Validation evidence should show at least:

```text
classify uses small
normal synthesis uses default
deep analysis task uses reasoning
override to small changes route
fallback from reasoning to default is logged
```
