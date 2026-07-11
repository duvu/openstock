# Tasks: Architecture gap remediation

## 0. Governance

- [x] 0.1 Preserve read-only research boundary.
- [x] 0.2 Preserve `vnalpha` console script compatibility.
- [x] 0.3 Preserve existing TUI single-composer workflow.
- [x] 0.4 Do not implement broker/account/order/portfolio/allocation/execution features.
- [x] 0.5 Do not merge without tests and validation evidence.
- [x] 0.6 Keep runtime behavior stable unless explicitly covered by this OpenSpec.

## 1. Split CLI entrypoint

- [ ] 1.1 Create `vnalpha/src/vnalpha/cli/` package.
- [ ] 1.2 Add `cli/app.py` for root Typer app and registration.
- [ ] 1.3 Add `cli/common.py` for dotenv/logging/connection helpers.
- [ ] 1.4 Move sync commands to `cli/sync.py`.
- [ ] 1.5 Move build commands to `cli/build.py`.
- [ ] 1.6 Move score command to `cli/score.py`.
- [ ] 1.7 Move watchlist command to `cli/watchlist.py`.
- [ ] 1.8 Move TUI launcher to `cli/tui.py`.
- [ ] 1.9 Move outcome commands to `cli/outcome.py`.
- [ ] 1.10 Add placeholder modules for `cli/context.py`, `cli/model.py`, and `cli/research.py` if runtime commands are not implemented yet.
- [x] 1.11 Convert `vnalpha/cli.py` into compatibility shim importing `app`.
- [x] 1.12 Add CLI import/registration tests.

## 2. Central policy package

- [x] 2.1 Add `vnalpha/src/vnalpha/policy/__init__.py`.
- [x] 2.2 Add `policy/permissions.py`.
- [x] 2.3 Add `policy/tool_policy.py`.
- [x] 2.4 Add `policy/assistant_policy.py`.
- [x] 2.5 Add `policy/command_policy.py`.
- [x] 2.6 Add `policy/safety_policy.py`.
- [x] 2.7 Define `ToolPolicyEntry` or equivalent.
- [x] 2.8 Define canonical tool policy map.
- [x] 2.9 Define canonical assistant allowlist from policy.
- [x] 2.10 Define canonical permission map from policy.
- [x] 2.11 Add policy tests.

## 3. Migrate tools to policy

- [x] 3.1 Update `tools.setup.TOOL_PERMISSIONS` to consume policy.
- [x] 3.2 Update `build_local_tool_registry()` to use policy metadata where feasible.
- [x] 3.3 Ensure all registered tools have policy entries.
- [x] 3.4 Add test: policy map and registry tool names match.
- [x] 3.5 Add test: mutating tools are explicitly marked.

## 4. Migrate assistant allowlists to policy

- [x] 4.1 Remove hardcoded `ASSISTANT_TOOL_ALLOWLIST` from assistant executor or make it imported from policy.
- [x] 4.2 Remove hardcoded `TOOL_ALLOWLIST` from assistant planner or make it imported from policy.
- [x] 4.3 Ensure planner and executor consume the same assistant allowlist.
- [x] 4.4 Remove `data.fetch` from assistant autonomous allowlist.
- [x] 4.5 Convert `fetch_data` intent to refusal/manual-command suggestion, or remove it from planner.
- [x] 4.6 Add test: `data.fetch` not allowed for assistant.
- [x] 4.7 Add test: planner cannot build assistant plan with `data.fetch`.
- [x] 4.8 Add test: executor rejects `data.fetch` assistant step.

## 5. TUI routing refactor

- [x] 5.1 Add `vnalpha/src/vnalpha/tui/routing/__init__.py`.
- [x] 5.2 Add `tui/routing/router.py`.
- [x] 5.3 Add `tui/routing/command_path.py`.
- [x] 5.4 Add `tui/routing/chat_path.py`.
- [x] 5.5 Add `tui/routing/status_adapter.py`.
- [x] 5.6 Add `tui/routing/lifecycle_hooks.py`.
- [x] 5.7 Add `tui/routing/events.py`.
- [x] 5.8 Keep `vnalpha.tui.input_router.TuiInputRouter` compatibility.
- [x] 5.9 Move command execution/render logic out of router.
- [x] 5.10 Move chat execution/render logic out of router.
- [x] 5.11 Move status mapping into status adapter.
- [x] 5.12 Add no-op lifecycle hook interface for workspace/todo/model integration.
- [x] 5.13 Add TUI routing tests.

## 6. Command result status semantics

- [ ] 6.1 Extend/standardize `CommandResult.status` values: `SUCCESS`, `PARTIAL`, `EMPTY`, `FAILED`, `VALIDATION_ERROR`.
- [ ] 6.2 Update textual/rich renderers to handle `EMPTY`.
- [x] 6.3 Update textual/rich renderers to handle `PARTIAL`.
- [x] 6.4 Update TUI status adapter mapping for `EMPTY`.
- [x] 6.5 Update TUI status adapter mapping for `PARTIAL`.
- [x] 6.6 Update `/explain` no-score path to return `EMPTY` or `PARTIAL`, not plain `SUCCESS`.
- [x] 6.7 Update `/compare` no-score path to return `EMPTY`.
- [x] 6.8 Update `/scan` no candidates path to return `EMPTY` if applicable.
- [x] 6.9 Update `/filter` no rows path to return `EMPTY` if applicable.
- [x] 6.10 Add command status tests.

## 7. data_availability refactor

- [x] 7.1 Add `data_availability/planner.py`.
- [x] 7.2 Add `data_availability/actions.py`.
- [ ] 7.3 Add `data_availability/executor.py`.
- [x] 7.4 Add `data_availability/service.py`.
- [x] 7.5 Keep public `ensure_symbol_analysis_ready()` API compatible.
- [x] 7.6 Move action planning out of long procedural function.
- [ ] 7.7 Move action execution into executor.
- [x] 7.8 Preserve dependency-injection hooks for tests.
- [x] 7.9 Preserve DATA_ENSURE_* observability events.
- [x] 7.10 Add enriched result fields without breaking `to_panel_dict()`.
- [x] 7.11 Add tests for cache hit, missing canonical, missing benchmark, missing features, missing score.
- [x] 7.12 Add test for planned actions.
- [x] 7.13 Add test for action execution with injected fakes.

## 8. model_routing package boundary

- [x] 8.1 Add `vnalpha/src/vnalpha/model_routing/__init__.py`.
- [x] 8.2 Add minimal README/doc reference or stub module if full runtime is handled by separate OpenSpec.
- [x] 8.3 Ensure no model routing logic is added ad hoc into TUI router.
- [x] 8.4 Ensure LLM gateway remains backward compatible.

## 9. workspace_context package boundary

- [x] 9.1 Add `vnalpha/src/vnalpha/workspace_context/__init__.py`.
- [x] 9.2 Add minimal README/doc reference or stub module if full runtime is handled by separate OpenSpec.
- [x] 9.3 Ensure no workspace context lifecycle logic is added ad hoc into TUI router.
- [x] 9.4 Ensure future integration point is lifecycle hooks.

## 10. Architecture tests

- [x] 10.1 Add `tests/test_architecture_boundaries.py`.
- [x] 10.2 Test CLI shim import.
- [x] 10.3 Test no hardcoded assistant allowlist outside policy.
- [x] 10.4 Test assistant allowlist excludes `data.fetch`.
- [x] 10.5 Test registry and policy tool names align.
- [x] 10.6 Test no TUI imports from warehouse in widgets where feasible.
- [x] 10.7 Test TUI default layout constraints still pass.
- [x] 10.8 Test new routing modules import.

## 11. Documentation

- [x] 11.1 Add `vnalpha/docs/architecture.md`.
- [x] 11.2 Add `vnalpha/docs/package-boundaries.md`.
- [x] 11.3 Update `vnalpha/docs/tui-workspace.md` with routing package design.
- [x] 11.4 Document CLI split.
- [x] 11.5 Document central policy source of truth.
- [x] 11.6 Document assistant no-autonomous-data-fetch rule.
- [x] 11.7 Document data availability flow.
- [x] 11.8 Document future package boundaries for model routing and workspace context.

## 12. Validation

- [x] 12.1 Run `make test-vnalpha`.
- [x] 12.2 Run `make lint-vnalpha`.
- [x] 12.3 Run `make verify-r4`.
- [x] 12.4 Run `openstock-verify --ci`.
- [x] 12.5 Add validation evidence for CLI compatibility.
- [x] 12.6 Add validation evidence for assistant policy migration.
- [x] 12.7 Add validation evidence for TUI routing compatibility.
- [x] 12.8 Add validation evidence for command status semantics.
- [x] 12.9 Add validation evidence for data_availability API compatibility.

## Reconciliation note

The validated compatibility-equivalent implementation is `cli.py` plus
`cli_app/`, `CommandStatus.EMPTY_RESULT`, and service-owned data-availability
action execution. Tasks 1.1-1.10, 6.1-6.2, and 7.3/7.7 remain unchecked because
their literal structural requirements conflict with those preserved public
contracts. Evidence and validation commands are recorded in
`vnalpha/docs/superpowers/plans/2026-07-11-architecture-gap-remediation-evidence-matrix.md`.
