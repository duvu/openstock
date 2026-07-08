# Tasks: Architecture gap refactor

## 0. Governance

- [ ] 0.1 Treat this as behavior-preserving architecture hardening.
- [ ] 0.2 Do not implement deep research features in this change.
- [ ] 0.3 Do not implement full workspace context lifecycle in this change unless separately scoped.
- [ ] 0.4 Do not implement full TODO panel behavior in this change unless separately scoped.
- [ ] 0.5 Preserve existing user-facing CLI commands.
- [ ] 0.6 Preserve existing slash command behavior unless explicitly corrected by result semantics.
- [ ] 0.7 Preserve read-only research boundary.
- [ ] 0.8 Do not mark complete without tests and validation evidence.

## 1. CLI modularisation

- [ ] 1.1 Create modular CLI package or `cli_app` package if `cli.py` name collision prevents `cli/` package.
- [ ] 1.2 Move Typer app creation to `cli_app/app.py` or `cli/app.py`.
- [ ] 1.3 Move common env/logging helpers to `common.py`.
- [ ] 1.4 Move sync commands to `sync.py`.
- [ ] 1.5 Move build commands to `build.py`.
- [ ] 1.6 Move score command to `score.py`.
- [ ] 1.7 Move watchlist command to `watchlist.py`.
- [ ] 1.8 Move TUI launch command to `tui.py`.
- [ ] 1.9 Move outcome commands to `outcome.py`.
- [ ] 1.10 Keep `vnalpha.cli:app` working.
- [ ] 1.11 Add CLI compatibility tests.

## 2. Central policy package

- [ ] 2.1 Add `vnalpha/policy/__init__.py`.
- [ ] 2.2 Add `permissions.py` or re-export existing `ToolPermission` safely.
- [ ] 2.3 Add `tool_policy.py` with central tool capability definitions.
- [ ] 2.4 Add `command_policy.py` for command metadata or command permission mapping.
- [ ] 2.5 Add `assistant_policy.py` for assistant/autonomous allowlist derivation.
- [ ] 2.6 Add `safety_policy.py` for research-only boundary constants if useful.
- [ ] 2.7 Ensure every local tool has a policy entry.
- [ ] 2.8 Add tests for policy completeness.

## 3. Remove duplicated allowlists

- [ ] 3.1 Refactor `assistant.executor` allowlist to derive from central policy.
- [ ] 3.2 Refactor `assistant.planner` allowlist to derive from central policy.
- [ ] 3.3 Refactor `tools.setup.TOOL_PERMISSIONS` to derive from central policy or assert equivalence.
- [ ] 3.4 Refactor command registry permissions to align with central policy.
- [ ] 3.5 Add tests proving planner/executor/tool permissions remain consistent.

## 4. Remove assistant autonomous `data.fetch`

- [ ] 4.1 Mark `data.fetch` as mutating warehouse in policy.
- [ ] 4.2 Set `allowed_for_assistant=false` for `data.fetch`.
- [ ] 4.3 Set `allowed_for_autonomous_plan=false` for `data.fetch`.
- [ ] 4.4 Remove `data.fetch` from assistant executor allowlist.
- [ ] 4.5 Remove `data.fetch` from planner allowlist.
- [ ] 4.6 Change `fetch_data` intent planning to refusal or explicit-command guidance.
- [ ] 4.7 Keep deterministic `ensure_symbol_analysis_ready()` path for analysis tools.
- [ ] 4.8 Add tests proving assistant cannot call `data.fetch`.
- [ ] 4.9 Add tests proving `/explain` still auto-provisions through ensure-data.

## 5. TUI router refactor

- [ ] 5.1 Add `vnalpha/tui/routing/__init__.py`.
- [ ] 5.2 Add `routing/router.py`.
- [ ] 5.3 Add `routing/command_path.py`.
- [ ] 5.4 Add `routing/chat_path.py`.
- [ ] 5.5 Add `routing/status_adapter.py`.
- [ ] 5.6 Add `routing/lifecycle_hooks.py`.
- [ ] 5.7 Add `routing/events.py`.
- [ ] 5.8 Keep `vnalpha.tui.input_router.TuiInputRouter` import path working.
- [ ] 5.9 Move command execution/rendering into command path.
- [ ] 5.10 Move chat execution/rendering into chat path.
- [ ] 5.11 Move status mapping into status adapter.
- [ ] 5.12 Move audit event helpers into events module.
- [ ] 5.13 Add tests for router delegation.

## 6. TUI layout boundary

- [ ] 6.1 Add `vnalpha/tui/responsive_layout.py` skeleton or boundary if not already present.
- [ ] 6.2 Add layout policy tests or placeholders for future TODO panel.
- [ ] 6.3 Ensure default layout remains StatusBar + OutputStream + ComposerInput + FooterHint.
- [ ] 6.4 Add mounted DOM tests where feasible.
- [ ] 6.5 Preserve one Textual Input.
- [ ] 6.6 Preserve no ContentSwitcher and no secondary ChatPanel.

## 7. Model routing boundary

- [ ] 7.1 Add `vnalpha/model_routing/__init__.py`.
- [ ] 7.2 Add `models.py` with `ModelProfile` and `ModelRouteDecision`.
- [ ] 7.3 Add `config.py` with env-backed profile config skeleton.
- [ ] 7.4 Add `policy.py` with deterministic default profile rules skeleton.
- [ ] 7.5 Add `resolver.py` with profile-to-model resolution.
- [ ] 7.6 Add `overrides.py` with session/workspace override skeleton.
- [ ] 7.7 Add `observability.py` with model route event helpers.
- [ ] 7.8 Add `integration.py` for gateway integration helpers.
- [ ] 7.9 Update `assistant.gateway.LLMGatewayClient.chat()` signature to accept `task_type`, `model_profile`, and `route_metadata`.
- [ ] 7.10 Preserve current `VNALPHA_LLM_MODEL` behavior as default.
- [ ] 7.11 Add gateway compatibility tests.

## 8. Workspace context boundary

- [ ] 8.1 Add `vnalpha/workspace_context/__init__.py`.
- [ ] 8.2 Add minimal `models.py`.
- [ ] 8.3 Add minimal `storage.py` boundary.
- [ ] 8.4 Add minimal `lifecycle.py` boundary.
- [ ] 8.5 Add minimal `integration.py` boundary.
- [ ] 8.6 Do not implement full lifecycle unless separately scoped.
- [ ] 8.7 Add import tests.

## 9. Data availability service split

- [ ] 9.1 Add `data_availability/planner.py`.
- [ ] 9.2 Add `data_availability/actions.py`.
- [ ] 9.3 Add `data_availability/service.py`.
- [ ] 9.4 Keep `ensure.py` as backward-compatible wrapper or thin orchestration layer.
- [ ] 9.5 Separate check/plan/action/execute phases.
- [ ] 9.6 Add `EnsureDataPlan` model if needed.
- [ ] 9.7 Extend `EnsureDataResult` with freshness/lineage fields.
- [ ] 9.8 Add planning-only tests.
- [ ] 9.9 Add wrapper compatibility tests.

## 10. Command result semantics

- [ ] 10.1 Add `CommandStatus` enum or constants.
- [ ] 10.2 Add statuses or helper methods for `EMPTY_RESULT` and `PARTIAL`.
- [ ] 10.3 Update `/explain` no-score path to avoid plain `SUCCESS`.
- [ ] 10.4 Update `/compare` no-records path to avoid plain `SUCCESS`.
- [ ] 10.5 Update renderer handling for new statuses.
- [ ] 10.6 Update session status mapping.
- [ ] 10.7 Add command status tests.

## 11. Remove stale phase coupling

- [ ] 11.1 Remove or update Phase 5.8/5.9 wording from assistant executor comments.
- [ ] 11.2 Remove or update Phase 5.8/5.9 wording from planner comments.
- [ ] 11.3 Remove or update Phase wording from tools setup comments.
- [ ] 11.4 Replace with capability-based language.
- [ ] 11.5 Add grep-style regression test or docs check if feasible.

## 12. Architecture docs

- [ ] 12.1 Add `vnalpha/docs/architecture.md`.
- [ ] 12.2 Add `vnalpha/docs/package-boundaries.md`.
- [ ] 12.3 Update `vnalpha/docs/tui-workspace.md` if TUI router paths change.
- [ ] 12.4 Document target CLI tree.
- [ ] 12.5 Document policy source of truth.
- [ ] 12.6 Document assistant mutation boundary.
- [ ] 12.7 Document model routing boundary.
- [ ] 12.8 Document workspace context boundary.

## 13. Regression tests

- [ ] 13.1 Add architecture boundary tests.
- [ ] 13.2 Add CLI app compatibility tests.
- [ ] 13.3 Add policy consistency tests.
- [ ] 13.4 Add assistant no-`data.fetch` tests.
- [ ] 13.5 Add TUI router import/delegation tests.
- [ ] 13.6 Add command result status tests.
- [ ] 13.7 Add gateway signature compatibility tests.
- [ ] 13.8 Add package import tests for new boundaries.

## 14. Validation

- [ ] 14.1 Run `make test-vnalpha`.
- [ ] 14.2 Run `make lint-vnalpha`.
- [ ] 14.3 Run `make verify-r4`.
- [ ] 14.4 Run `openstock-verify --ci`.
- [ ] 14.5 Add validation evidence for existing CLI command compatibility.
- [ ] 14.6 Add validation evidence for policy centralisation.
- [ ] 14.7 Add validation evidence that assistant cannot autonomously call `data.fetch`.
- [ ] 14.8 Add validation evidence for TUI layout/router regression tests.
