# Tasks: Architecture gap remediation

## 0. Governance

- [ ] 0.1 Preserve read-only research boundary.
- [ ] 0.2 Preserve `vnalpha` console script compatibility.
- [ ] 0.3 Preserve existing TUI single-composer workflow.
- [ ] 0.4 Do not implement broker/account/order/portfolio/allocation/execution features.
- [ ] 0.5 Do not merge without tests and validation evidence.
- [ ] 0.6 Keep runtime behavior stable unless explicitly covered by this OpenSpec.

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
- [ ] 1.11 Convert `vnalpha/cli.py` into compatibility shim importing `app`.
- [ ] 1.12 Add CLI import/registration tests.

## 2. Central policy package

- [ ] 2.1 Add `vnalpha/src/vnalpha/policy/__init__.py`.
- [ ] 2.2 Add `policy/permissions.py`.
- [ ] 2.3 Add `policy/tool_policy.py`.
- [ ] 2.4 Add `policy/assistant_policy.py`.
- [ ] 2.5 Add `policy/command_policy.py`.
- [ ] 2.6 Add `policy/safety_policy.py`.
- [ ] 2.7 Define `ToolPolicyEntry` or equivalent.
- [ ] 2.8 Define canonical tool policy map.
- [ ] 2.9 Define canonical assistant allowlist from policy.
- [ ] 2.10 Define canonical permission map from policy.
- [ ] 2.11 Add policy tests.

## 3. Migrate tools to policy

- [ ] 3.1 Update `tools.setup.TOOL_PERMISSIONS` to consume policy.
- [ ] 3.2 Update `build_local_tool_registry()` to use policy metadata where feasible.
- [ ] 3.3 Ensure all registered tools have policy entries.
- [ ] 3.4 Add test: policy map and registry tool names match.
- [ ] 3.5 Add test: mutating tools are explicitly marked.

## 4. Migrate assistant allowlists to policy

- [ ] 4.1 Remove hardcoded `ASSISTANT_TOOL_ALLOWLIST` from assistant executor or make it imported from policy.
- [ ] 4.2 Remove hardcoded `TOOL_ALLOWLIST` from assistant planner or make it imported from policy.
- [ ] 4.3 Ensure planner and executor consume the same assistant allowlist.
- [ ] 4.4 Remove `data.fetch` from assistant autonomous allowlist.
- [ ] 4.5 Convert `fetch_data` intent to refusal/manual-command suggestion, or remove it from planner.
- [ ] 4.6 Add test: `data.fetch` not allowed for assistant.
- [ ] 4.7 Add test: planner cannot build assistant plan with `data.fetch`.
- [ ] 4.8 Add test: executor rejects `data.fetch` assistant step.

## 5. TUI routing refactor

- [ ] 5.1 Add `vnalpha/src/vnalpha/tui/routing/__init__.py`.
- [ ] 5.2 Add `tui/routing/router.py`.
- [ ] 5.3 Add `tui/routing/command_path.py`.
- [ ] 5.4 Add `tui/routing/chat_path.py`.
- [ ] 5.5 Add `tui/routing/status_adapter.py`.
- [ ] 5.6 Add `tui/routing/lifecycle_hooks.py`.
- [ ] 5.7 Add `tui/routing/events.py`.
- [ ] 5.8 Keep `vnalpha.tui.input_router.TuiInputRouter` compatibility.
- [ ] 5.9 Move command execution/render logic out of router.
- [ ] 5.10 Move chat execution/render logic out of router.
- [ ] 5.11 Move status mapping into status adapter.
- [ ] 5.12 Add no-op lifecycle hook interface for workspace/todo/model integration.
- [ ] 5.13 Add TUI routing tests.

## 6. Command result status semantics

- [ ] 6.1 Extend/standardize `CommandResult.status` values: `SUCCESS`, `PARTIAL`, `EMPTY`, `FAILED`, `VALIDATION_ERROR`.
- [ ] 6.2 Update textual/rich renderers to handle `EMPTY`.
- [ ] 6.3 Update textual/rich renderers to handle `PARTIAL`.
- [ ] 6.4 Update TUI status adapter mapping for `EMPTY`.
- [ ] 6.5 Update TUI status adapter mapping for `PARTIAL`.
- [ ] 6.6 Update `/explain` no-score path to return `EMPTY` or `PARTIAL`, not plain `SUCCESS`.
- [ ] 6.7 Update `/compare` no-score path to return `EMPTY`.
- [ ] 6.8 Update `/scan` no candidates path to return `EMPTY` if applicable.
- [ ] 6.9 Update `/filter` no rows path to return `EMPTY` if applicable.
- [ ] 6.10 Add command status tests.

## 7. data_availability refactor

- [ ] 7.1 Add `data_availability/planner.py`.
- [ ] 7.2 Add `data_availability/actions.py`.
- [ ] 7.3 Add `data_availability/executor.py`.
- [ ] 7.4 Add `data_availability/service.py`.
- [ ] 7.5 Keep public `ensure_symbol_analysis_ready()` API compatible.
- [ ] 7.6 Move action planning out of long procedural function.
- [ ] 7.7 Move action execution into executor.
- [ ] 7.8 Preserve dependency-injection hooks for tests.
- [ ] 7.9 Preserve DATA_ENSURE_* observability events.
- [ ] 7.10 Add enriched result fields without breaking `to_panel_dict()`.
- [ ] 7.11 Add tests for cache hit, missing canonical, missing benchmark, missing features, missing score.
- [ ] 7.12 Add test for planned actions.
- [ ] 7.13 Add test for action execution with injected fakes.

## 8. model_routing package boundary

- [ ] 8.1 Add `vnalpha/src/vnalpha/model_routing/__init__.py`.
- [ ] 8.2 Add minimal README/doc reference or stub module if full runtime is handled by separate OpenSpec.
- [ ] 8.3 Ensure no model routing logic is added ad hoc into TUI router.
- [ ] 8.4 Ensure LLM gateway remains backward compatible.

## 9. workspace_context package boundary

- [ ] 9.1 Add `vnalpha/src/vnalpha/workspace_context/__init__.py`.
- [ ] 9.2 Add minimal README/doc reference or stub module if full runtime is handled by separate OpenSpec.
- [ ] 9.3 Ensure no workspace context lifecycle logic is added ad hoc into TUI router.
- [ ] 9.4 Ensure future integration point is lifecycle hooks.

## 10. Architecture tests

- [ ] 10.1 Add `tests/test_architecture_boundaries.py`.
- [ ] 10.2 Test CLI shim import.
- [ ] 10.3 Test no hardcoded assistant allowlist outside policy.
- [ ] 10.4 Test assistant allowlist excludes `data.fetch`.
- [ ] 10.5 Test registry and policy tool names align.
- [ ] 10.6 Test no TUI imports from warehouse in widgets where feasible.
- [ ] 10.7 Test TUI default layout constraints still pass.
- [ ] 10.8 Test new routing modules import.

## 11. Documentation

- [ ] 11.1 Add `vnalpha/docs/architecture.md`.
- [ ] 11.2 Add `vnalpha/docs/package-boundaries.md`.
- [ ] 11.3 Update `vnalpha/docs/tui-workspace.md` with routing package design.
- [ ] 11.4 Document CLI split.
- [ ] 11.5 Document central policy source of truth.
- [ ] 11.6 Document assistant no-autonomous-data-fetch rule.
- [ ] 11.7 Document data availability flow.
- [ ] 11.8 Document future package boundaries for model routing and workspace context.

## 12. Validation

- [ ] 12.1 Run `make test-vnalpha`.
- [ ] 12.2 Run `make lint-vnalpha`.
- [ ] 12.3 Run `make verify-r4`.
- [ ] 12.4 Run `openstock-verify --ci`.
- [ ] 12.5 Add validation evidence for CLI compatibility.
- [ ] 12.6 Add validation evidence for assistant policy migration.
- [ ] 12.7 Add validation evidence for TUI routing compatibility.
- [ ] 12.8 Add validation evidence for command status semantics.
- [ ] 12.9 Add validation evidence for data_availability API compatibility.
