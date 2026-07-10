# Review: Model routing profiles

## Verdict

OpenStock needs explicit model routing before adding heavier research workflows. A single static model choice is not adequate for a terminal research agent.

Correct target:

```text
small model for light stages
default model for normal responses
reasoning model for complex analysis
long-context model for large workspace synthesis
```

Incorrect target:

```text
LLM chooses its own model
hard-coded provider/model names in business logic
one expensive model for every stage
one weak model for every stage
silent fallback with no audit trail
```

## Main critique

### 1. Model selection must be deterministic

The model should be selected by policy code, not by the LLM. Otherwise routing becomes non-auditable and hard to test.

### 2. Model profiles are better than model ids in business logic

Business logic should request:

```text
small
default
reasoning
long_context
```

It should not directly embed provider-specific ids. Provider/model ids belong in config.

### 3. Stage-based routing should be the default

Assistant stages have different requirements:

```text
classify -> small
plan deterministic -> no LLM
synthesize -> default or reasoning
compact -> long_context or reasoning
```

### 4. Task-based routing should override stage defaults for complex workflows

Some synthesis stages are simple; some require serious reasoning. For example:

```text
summarize a small score record -> default
compare five symbols with caveats -> reasoning
generate shortlist rationale -> reasoning
compact huge workspace -> long_context
```

### 5. Override must exist but stay bounded

Users need to force a profile for debugging or cost control:

```text
/model use small
/model use reasoning
/model reset
```

But overrides should be profile-based, not arbitrary raw model id by default.

### 6. Fallback must be explicit

If the reasoning model fails, the system can fallback to default, but it must log and display the fallback when relevant.

Silent fallback causes misleading quality assumptions.

### 7. Routing must be visible in observability

For cost and quality debugging, every LLM call should log:

```text
profile
model_id
stage
task_type
route_reason
override_source
fallback
usage
latency
```

### 8. TUI should surface active profile compactly

TUI status/footer can show:

```text
model=default
model=reasoning override
```

Do not make model state noisy; expose detail through `/model status`.

## Suggested routing matrix

```text
Stage / task                         Profile
-------------------------------------------------
intent classification                small
simple command explanation           small/default
normal answer synthesis              default
tool output summary under threshold  default
deep symbol analysis                 reasoning
watchlist synthesis                   reasoning if large, default if small
shortlist generation                  reasoning
conditional scenario planning         reasoning
workspace compaction                  long_context or reasoning
error repair diagnosis                reasoning
short title generation                small
```

## Risks

### Risk: cost explosion

Mitigation:

```text
reasoning profile only for explicit complex tasks
configurable budget guardrails
log cost metadata
session override to small/default
```

### Risk: quality degradation from small model

Mitigation:

```text
small profile only for constrained tasks
fallback to default on invalid JSON or low-confidence output
schema validation
```

### Risk: hidden model drift

Mitigation:

```text
/model profiles shows resolved model ids
MODEL_ROUTE_SELECTED audit event
validation tests for config
```

### Risk: provider lock-in

Mitigation:

```text
profiles are provider-agnostic
model ids are config/env values
business logic never imports provider-specific constants
```

### Risk: unsafe arbitrary override

Mitigation:

```text
allow only configured profile names by default
raw model override disabled unless config explicitly permits it
```

## MVP recommendation

MVP should implement:

```text
ModelProfile enum
ModelRoutingPolicy
ModelProfileResolver
ModelRouteDecision
config/env support
assistant gateway integration
/model status
/model profiles
/model use <profile>
/model reset
MODEL_ROUTE_* audit events
tests
```

Defer:

```text
dynamic cost-based routing
online benchmark selection
per-user billing controls
raw model id override
provider health scoring
```
