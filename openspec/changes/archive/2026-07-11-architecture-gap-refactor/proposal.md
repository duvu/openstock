# Proposal: Architecture gap refactor

## Summary

Refactor OpenStock architecture to close the structural gaps identified in the latest codebase review before adding more agentic features.

This change focuses on architecture hardening, package boundaries, policy centralisation, and tree organisation.

Primary gaps to close:

```text
1. Split monolithic vnalpha/cli.py into modular CLI package.
2. Centralise tool/command/assistant permission policy.
3. Refactor TUI router into smaller command/chat/status/lifecycle components.
4. Remove direct assistant access to data.fetch and route data mutation through deterministic data availability flows.
5. Add first-class model routing package and prepare gateway for profile-based selection.
6. Introduce workspace_context package boundary for future context lifecycle implementation.
7. Restructure data_availability from one procedural workflow into check/plan/action/execution service boundaries.
8. Standardise command result semantics for empty/partial/failure outcomes.
9. Remove phase-label coupling from core assistant/tool architecture docs and comments.
10. Add architecture documentation and regression tests for directory/package boundaries.
```

This is an implementation OpenSpec. Runtime changes should be incremental and backward-compatible.

## Why

OpenStock has grown from a score-based screener into a terminal research workspace with:

```text
TUI
assistant
commands
tools
data provisioning
observability
outcome evaluation
future workspace context
future TODO panel
future model routing
future deep research intelligence
```

The codebase is still manageable, but several modules are starting to concentrate too many responsibilities:

```text
vnalpha/cli.py
vnalpha/tui/input_router.py
assistant planner/executor allowlists
tools setup permissions
data_availability.ensure
```

If these are not cleaned up before adding more capabilities, future work will become brittle and inconsistent.

## Current problems

### CLI entrypoint is too large

`vnalpha/cli.py` contains Typer app wiring, env loading, logging setup, sync/build/score/watchlist/tui/outcome commands, DB connection, migration calls, and output rendering.

### Policy is duplicated

Tool permissions and allowlists exist in multiple places:

```text
assistant.executor ASSISTANT_TOOL_ALLOWLIST
assistant.planner TOOL_ALLOWLIST
tools.setup TOOL_PERMISSIONS
commands.setup command registry permissions
```

This creates drift risk.

### TUI router is too broad

`TuiInputRouter` owns controller setup, command executor setup, route decisions, rendering, status updates, busy state, plan approval/cancel, and observability.

### Assistant has a direct data mutation path

`data.fetch` is a WRITE_DATA tool exposed to assistant planner/executor. Data mutation should instead flow through deterministic data availability preconditions or explicit user commands.

### LLM Gateway uses a single static model

Gateway currently resolves one model from env. There is no profile-based model routing for small/default/reasoning/long-context tasks.

### Data availability workflow is too procedural

`ensure_symbol_analysis_ready()` mixes checks, decisions, actions, result mutation, and observability in one workflow function.

### Command result semantics are too coarse

Commands can return `SUCCESS` even when no score/data exists. This makes downstream TUI/assistant/status handling ambiguous.

## Goals

- Improve package boundaries without breaking user-facing behavior.
- Split CLI into modular command files.
- Introduce central policy source of truth for tools/commands/assistant access.
- Shrink TUI router into focused components.
- Remove assistant direct `data.fetch` mutation path.
- Add model routing package skeleton and gateway integration contract.
- Add workspace context package skeleton and integration boundary.
- Refactor data availability into check/plan/action/service modules.
- Add richer command result statuses or equivalent result classification.
- Update docs to describe target architecture.
- Add regression tests that prevent reintroducing known architecture smells.

## Non-goals

- Do not implement deep symbol analysis in this change.
- Do not implement full workspace context lifecycle in this change.
- Do not implement responsive TODO panel in this change.
- Do not implement trading execution, broker integration, account actions, or allocation workflows.
- Do not rewrite the scoring model.
- Do not change persisted warehouse schemas unless needed for command/session semantics.
- Do not break existing CLI commands.
- Do not remove legacy importable TUI screens unless separately specified.

## Target package layout

### CLI

```text
vnalpha/cli.py                    # compatibility shim only
vnalpha/cli/
├── __init__.py
├── app.py
├── common.py
├── sync.py
├── build.py
├── score.py
├── watchlist.py
├── tui.py
├── outcome.py
├── context.py                    # skeleton or future hook
├── model.py                      # skeleton or future hook
└── research.py                   # future hook
```

### Policy

```text
vnalpha/policy/
├── __init__.py
├── permissions.py
├── tool_policy.py
├── command_policy.py
├── assistant_policy.py
└── safety_policy.py
```

### TUI

```text
vnalpha/tui/
├── app.py
├── input_history.py
├── runtime_status.py
├── responsive_layout.py          # future/TODO panel boundary
├── routing/
│   ├── __init__.py
│   ├── router.py
│   ├── command_path.py
│   ├── chat_path.py
│   ├── status_adapter.py
│   └── lifecycle_hooks.py
└── widgets/
    ├── output_stream.py
    ├── composer_input.py
    ├── status_bar.py
    ├── footer_hint.py
    └── todo_panel.py             # future boundary, not necessarily implemented here
```

### Model routing

```text
vnalpha/model_routing/
├── __init__.py
├── models.py
├── config.py
├── policy.py
├── resolver.py
├── overrides.py
├── observability.py
└── integration.py
```

### Workspace context

```text
vnalpha/workspace_context/
├── __init__.py
├── models.py
├── storage.py
├── lifecycle.py
├── compaction.py
├── cleaning.py
├── export.py
├── integration.py
└── observability.py
```

### Data availability

```text
vnalpha/data_availability/
├── __init__.py
├── models.py
├── policy.py
├── checks.py
├── planner.py
├── actions.py
├── service.py
├── observability.py
└── ensure.py                    # backward-compatible wrapper
```

## Success criteria

This change is complete when:

```text
- existing CLI commands still work through the same `vnalpha` entrypoint
- cli.py is reduced to a compatibility shim or thin import layer
- central policy module becomes the source of truth for assistant/tool permissions
- assistant planner/executor no longer duplicate allowlists manually
- assistant no longer directly exposes WRITE_DATA `data.fetch` in autonomous plan allowlist
- TUI routing logic is split into command/chat/status/lifecycle components
- data availability has explicit check/plan/action/service boundaries
- model routing package exists and gateway accepts routing metadata even if full profile behavior is implemented later
- workspace_context package boundary exists for lifecycle integration
- command result status semantics distinguish success, empty, partial, failed, and validation errors
- architecture docs are updated
- regression tests protect package boundaries and known anti-patterns
```

## Completion principle

Do not mark complete because files were moved. Completion requires behavior-preserving refactor, centralised policy, removed duplicated allowlists, safer assistant mutation boundaries, updated docs, and tests.
