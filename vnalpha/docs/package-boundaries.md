# Package boundaries

This reference names the packages that own the architecture boundaries in the
current `vnalpha` implementation. Public compatibility imports remain valid
where noted.

## `vnalpha.cli_app`

Owns Typer application composition and command registration. Command modules
are separated by domain. `vnalpha.cli:app` remains the public compatibility
entrypoint through the `vnalpha.cli` shim.

## `vnalpha.policy`

Owns central policy. `tool_policy.py` defines `TOOL_CAPABILITIES` and derived
permission mappings. `assistant_policy.py` derives assistant and autonomous
plan tool names from those capabilities. `data.fetch` is a command-eligible,
warehouse-mutating capability, not an assistant or autonomous-plan capability.

## `vnalpha.data_availability`

Owns data-readiness planning and execution:

```text
checks.py     inspect current warehouse state
planner.py    derive an EnsureDataPlan and actions
actions.py    provide sync, build, and score dependencies
service.py    execute the planned actions and assemble the result
ensure.py     keep ensure_symbol_analysis_ready() compatible
```

The planner can derive actions without executing them. The service owns action
execution. `ensure_symbol_analysis_ready()` remains the compatibility wrapper
used by analysis callers.

## `vnalpha.model_routing`

Owns env-backed routing configuration, profile policy, overrides, resolver,
and route observability. It preserves `VNALPHA_LLM_MODEL` as the default-model
behavior when no profile is chosen.

## `vnalpha.workspace_context`

Owns importable workspace models, storage, lifecycle, and integration helpers.
It provides a boundary for lifecycle work without making a claim that this
architecture change implements the complete workspace lifecycle.

## `vnalpha.tui.routing`

Owns TUI route selection and focused paths:

```text
routing/router.py            route selection and orchestration
routing/command_path.py      command execution and rendering
routing/chat_path.py         chat execution and rendering
routing/status_adapter.py    route activity to runtime status mapping
routing/lifecycle_hooks.py   controller and connection setup hooks
routing/events.py            routed-input and render-error event helpers
```

`vnalpha.tui.input_router.TuiInputRouter` remains a compatibility import for
`vnalpha.tui.routing.router.TuiInputRouter`.

## Command result boundary

`vnalpha.commands.models` owns `CommandStatus` and `CommandResult` semantics.
Renderers and session status mapping consume those statuses instead of treating
empty or partial results as plain success.

## Non-goals

These boundaries do not add deep research, a complete workspace lifecycle, or
complete TODO behavior. They document the currently shipped package structure
and compatibility paths only.
