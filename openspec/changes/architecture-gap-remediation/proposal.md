# Proposal: Architecture gap remediation

## Summary

Refactor the OpenStock / vnalpha codebase to close the architecture gaps found during the latest codebase review.

This change targets system architecture, package boundaries, tree structure, and governance before adding more agentic capabilities.

Primary remediation areas:

```text
1. Split monolithic CLI entrypoint
2. Centralize command/tool/assistant policy and permissions
3. Refactor TUI router responsibilities
4. Remove assistant autonomous access to data.fetch
5. Normalize command result status semantics
6. Prepare model_routing as first-class package boundary
7. Prepare workspace_context as first-class package boundary
8. Restructure data_availability into check/plan/action/execute/result layers
9. Replace source-inspection-only TUI tests with real layout/DOM tests where feasible
10. Update architecture docs and dependency direction rules
```

This is an implementation OpenSpec. Runtime implementation should happen in a follow-up PR after this spec is reviewed.

## Why

The codebase has a solid MVP structure, but it is now growing in multiple directions:

```text
- TUI workspace
- assistant planning/execution/synthesis
- slash commands
- local tools
- data provisioning
- observability
- workspace context lifecycle
- TODO side panel
- model routing
- deep research intelligence
```

Without an architecture remediation pass, new features will increase coupling and duplicate policy logic.

## Problems found

### Problem 1: `vnalpha/cli.py` is becoming a god entrypoint

It currently owns Typer app creation, env loading, logging init, warehouse connection bootstrapping, command definitions, rendering, and many domain command flows.

Future commands such as `/model`, `/context`, `/todo`, `/shortlist`, and `/research-plan` will make it larger unless split.

### Problem 2: Policy and allowlists are duplicated

Tool allowlists and permissions are spread across:

```text
assistant.executor
assistant.planner
tools.setup
commands.setup
```

This creates drift risk.

### Problem 3: `data.fetch` is exposed to assistant autonomous tool planning

The assistant allowlist includes `data.fetch`, even though deterministic data provisioning now exists through `data_availability.ensure`.

The assistant should not decide when to mutate warehouse data. Data readiness should be a deterministic precondition of analysis tools.

### Problem 4: `TuiInputRouter` is overburdened

The router currently handles route decisions, command execution, chat dispatch, status mapping, render callbacks, approve/cancel, busy state, and observability.

Upcoming workspace context, TODO panel, model status, and lifecycle hooks will make this worse.

### Problem 5: Command result status semantics are too coarse

Some handlers return `SUCCESS` for empty/no-score outcomes. The architecture needs distinct semantics for success, partial, empty, failed, and validation errors.

### Problem 6: `data_availability.ensure` is procedural and hard to extend

The ensure flow mixes checking, planning, action execution, logging, and final result assembly in one long function.

It should evolve toward:

```text
check -> plan actions -> execute actions -> final check -> result
```

### Problem 7: Model selection is static

`LLMGatewayClient` currently resolves a single model from environment config. The system needs a package boundary for model profiles and routing.

### Problem 8: Workspace context is not yet a package boundary

Workspace context lifecycle is now required. It should not be embedded in TUI router or command handlers ad hoc.

### Problem 9: TUI tests are partly source-inspection based

Source-inspection tests help, but real mounted-layout tests are needed for one-output, one-composer, one-input, status bar, and future responsive TODO panel behavior.

## Goals

- Keep user-visible behavior stable where possible.
- Split CLI into modular subcommands without breaking `vnalpha` console script.
- Create central policy/permissions source of truth.
- Remove `data.fetch` from assistant autonomous planning and execution allowlists.
- Refactor TUI routing into smaller adapters/paths.
- Add command result status semantics for empty/partial outcomes.
- Restructure data availability around explicit check/plan/execute/result components.
- Add package boundaries for `model_routing` and `workspace_context`.
- Improve tests so architecture constraints are enforced by behavior/DOM tests, not only source inspection.
- Update docs to describe final dependency direction and package responsibilities.

## Non-goals

- Do not implement deep symbol analysis in this change.
- Do not implement full workspace context lifecycle in this change unless already covered by its own OpenSpec.
- Do not implement full model routing runtime unless already covered by its own OpenSpec.
- Do not add broker, order, account, portfolio, allocation, or execution functionality.
- Do not change the read-only research boundary.
- Do not delete legacy TUI screens; keep them importable but not mounted by default.
- Do not rewrite the whole system in one large risky patch.

## Target package shape

### CLI

```text
vnalpha/cli.py                 # compatibility shim only
vnalpha/cli/
├── __init__.py
├── app.py
├── common.py
├── sync.py
├── build.py
├── score.py
├── watchlist.py
├── outcome.py
├── tui.py
├── context.py        # placeholder if feature not implemented
├── model.py          # placeholder if feature not implemented
└── research.py       # placeholder for future research commands
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

### TUI routing

```text
vnalpha/tui/routing/
├── __init__.py
├── router.py
├── command_path.py
├── chat_path.py
├── status_adapter.py
├── lifecycle_hooks.py
└── events.py
```

### Data availability

```text
vnalpha/data_availability/
├── checks.py
├── planner.py
├── actions.py
├── executor.py
├── service.py
├── models.py
├── policy.py
└── observability.py
```

### Future package boundaries

```text
vnalpha/model_routing/
vnalpha/workspace_context/
```

These may initially contain package skeletons and docs if runtime implementation is handled by separate OpenSpecs.

## Success criteria

This remediation is complete when:

```text
- `vnalpha` CLI entrypoint remains backward compatible
- CLI command definitions are split out of the monolithic `cli.py`
- central policy defines tool permissions and assistant allowlist
- planner, executor, and tool registry consume the same policy source
- assistant no longer autonomously plans or executes `data.fetch`
- TUI router is split into smaller route/path/status components
- command result status semantics support EMPTY/PARTIAL or equivalent
- `/explain` and `/compare` no longer return plain SUCCESS for no-score/empty outcomes
- data_availability has explicit check/plan/action/execute/service boundaries
- package boundaries for model_routing and workspace_context are documented or stubbed
- architecture tests enforce dependency direction and layout constraints
- docs describe tree structure and package responsibilities
```

## Completion principle

Do not mark this complete by only moving files. Completion requires behavior compatibility, policy de-duplication, removal of assistant autonomous data mutation, tests, and updated architecture docs.
