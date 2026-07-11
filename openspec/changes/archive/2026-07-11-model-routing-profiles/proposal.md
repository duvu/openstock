# Proposal: Model routing profiles

## Summary

Add configurable model routing profiles so OpenStock can choose different LLM models for different workload classes, similar to the model profile behavior used by agentic coding tools.

The system should support:

```text
- default model for normal assistant work
- small model for lightweight tasks
- reasoning model for high-complexity tasks
- optional large/context model for long-context synthesis
- deterministic task-to-profile routing
- user/workspace/session overrides
- fallback when selected model fails
- observability for chosen model/profile/cost metadata
```

This should be integrated into the assistant gateway, planner/synthesizer stages, TUI status, and config docs.

## Why

The assistant currently treats model usage as a mostly static gateway concern. As the system grows, different stages need different model economics and capabilities.

Examples:

```text
small model:
- classify intent
- rewrite short command output
- summarize small tool result
- generate title
- route simple slash command help

default model:
- normal natural-language answer
- explain persisted score
- summarize watchlist
- answer workspace follow-up

reasoning model:
- deep symbol analysis
- shortlist reasoning
- conditional scenario plan
- error diagnosis
- multi-step research planning
- compare several candidates with caveats

long-context model:
- compact workspace context
- synthesize large watchlist or long artifact set
```

Without routing, the system either wastes expensive models on small tasks or underpowers reasoning-heavy tasks.

## Problem statement

OpenStock needs a first-class model selection policy. The policy must be explicit, testable, observable, and overridable.

The target behavior:

```text
Assistant stage or command starts
  -> classify task/stage complexity
  -> select model profile: small/default/reasoning/long_context
  -> resolve actual provider/model id from config
  -> call LLM Gateway with selected model
  -> log model profile/model id/route reason/tokens/cost metadata
  -> fallback if the selected model fails
```

## Goals

- Add model profile configuration.
- Add `small`, `default`, `reasoning`, and optional `long_context` profiles.
- Add deterministic routing by assistant stage and task type.
- Allow explicit user/session/workspace override.
- Allow command-level override for debugging.
- Preserve safe allowlist of permitted models.
- Add fallback policy.
- Add model route observability.
- Surface current model/profile in TUI status or `/model status`.
- Add tests for routing, override, fallback, and audit events.

## Non-goals

- Do not auto-select models based on external pricing APIs.
- Do not let the LLM choose its own model.
- Do not bypass internal LLM Gateway policy.
- Do not expose secret provider credentials.
- Do not create a second assistant pipeline.
- Do not make every command require LLM usage.
- Do not weaken existing unsupported/unsafe request handling.

## Model profiles

Minimum profiles:

```text
small
  for cheap/fast/simple tasks

default
  for normal assistant responses

reasoning
  for complex multi-step analysis and planning

long_context
  optional, for compacting/synthesizing large workspace artifacts
```

Each profile should resolve to a configured model id:

```text
model_profiles:
  small: <provider/model-small>
  default: <provider/model-default>
  reasoning: <provider/model-reasoning>
  long_context: <provider/model-long-context>
```

The actual values should come from config/env and must not be hard-coded into business logic.

## Routing examples

```text
classify intent              -> small
build deterministic plan     -> no LLM
synthesize normal answer     -> default
summarize watchlist          -> default or reasoning if large
deep symbol analysis         -> reasoning
shortlist generation         -> reasoning
research scenario plan       -> reasoning
workspace compact            -> long_context or reasoning
short title generation       -> small
fallback summary after error -> small/default depending size
```

## Commands

Add model management commands:

```text
/model status
/model profiles
/model use <profile>
/model use default
/model reset
/model explain-route <task-or-stage>
```

Optional aliases:

```text
/model small
/model reasoning
/model default
```

These commands should update session/workspace preference, not global config, unless explicitly configured later.

## Override precedence

Suggested precedence:

```text
1. explicit per-call override
2. session/workspace override from /model use
3. task/stage routing policy
4. configured default profile
5. hard-coded safe fallback profile
```

## Observability

Every LLM call should log:

```text
MODEL_ROUTE_SELECTED
MODEL_CALL_STARTED
MODEL_CALL_SUCCEEDED
MODEL_CALL_FAILED
MODEL_FALLBACK_USED
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
estimated_cost if available
correlation_id
```

## Success criteria

This change is complete only when:

```text
- model profiles are configurable
- small/default/reasoning profiles are supported
- assistant classify stage uses small profile
- normal synthesis uses default profile
- complex research tasks use reasoning profile
- workspace compaction can use long_context or reasoning profile
- /model status shows active profile and resolved model ids
- /model use <profile> overrides current session/workspace
- /model reset restores routing policy
- fallback works when selected profile fails
- model route decisions are logged
- tests cover profile resolution, routing, override, fallback, and command behavior
```

## Completion principle

Do not mark this complete by adding environment variables only. Completion requires an actual routing policy, integration with LLM Gateway calls, commands, observability, and tests.
