# Architecture boundaries

This document describes package boundaries that are present in the current
`vnalpha` source tree. It is a map of ownership and compatibility contracts,
not a roadmap for unimplemented behavior.

## CLI application

The CLI implementation is split under `vnalpha.cli_app`:

```text
cli_app/
  app.py
  ask.py
  cmd.py
  common.py
  init.py
  log.py
  sync.py
  build.py
  score.py
  watchlist.py
  tui.py
  outcome.py
  outcome_evaluate.py
  outcome_performance.py
  outcome_report.py
  outcome_summary.py
```

`vnalpha.cli` is a compatibility shim that re-exports `app` from
`vnalpha.cli_app.app`. The console entrypoint remains `vnalpha.cli:app`.

## Central policy

`vnalpha.policy.tool_policy` is the immutable source of truth for local tool
capabilities. Its `ToolCapability` metadata supplies permission, command,
assistant, autonomous-plan, warehouse-mutation, and confirmation properties.
Consumers derive their tool permissions and assistant eligibility from this
policy rather than maintaining separate tool-name allowlists.

## Manual mutation and deterministic provisioning

`data.fetch` is a warehouse-mutating tool. It remains available through an
explicit command or local tool path, but the policy excludes it from assistant
execution and autonomous plans. Assistant requests to fetch data are refused
with explicit-command guidance.

Analysis paths use `ensure_symbol_analysis_ready()` instead. This
backward-compatible wrapper passes a request and injected dependencies to the
data-availability service, allowing deterministic provisioning for analysis
without granting the assistant direct `data.fetch` authority.

## Model routing

`vnalpha.model_routing` owns profile selection and model-route decisions.
`ModelProfile` represents small, default, reasoning, and long-context
profiles. `ModelRoutingConfig.from_env()` retains `VNALPHA_LLM_MODEL` as the
default model when no explicit routing profile overrides it. Gateway calls can
also accept stage, task type, profile, and route metadata.

## Workspace context

`vnalpha.workspace_context` is the import boundary for workspace state,
storage, lifecycle functions, and prompt integration. The TUI imports its
workspace helpers through `vnalpha.tui.workspace_context`, which delegates to
this package.

Workspace lifecycle behavior is owned by its separate workspace-context
change. This architecture change does not claim to implement a full workspace
lifecycle.

## Command outcomes

`vnalpha.commands.models.CommandStatus` distinguishes `SUCCESS`,
`EMPTY_RESULT`, `PARTIAL`, `FAILED`, and `VALIDATION_ERROR`. Command handlers
use empty or partial statuses when usable data is absent or provisioning is
incomplete, rather than reporting those outcomes as plain success.

## Non-goals

This architecture change does not implement deep research. It also does not
claim full workspace lifecycle behavior or full TODO panel behavior. The TUI
TODO rail and workspace lifecycle remain governed by their separately scoped
work.
