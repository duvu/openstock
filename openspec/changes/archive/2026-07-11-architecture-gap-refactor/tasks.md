# Tasks: Architecture gap refactor

## 0. Governance

- [x] 0.1 Treat this as behavior-preserving architecture hardening.
- [x] 0.2 Do not implement deep research features in this change.
- [x] 0.3 Do not implement full workspace context lifecycle in this change unless separately scoped.
- [x] 0.4 Do not implement full TODO panel behavior in this change unless separately scoped.
- [x] 0.5 Preserve existing user-facing CLI commands.
- [x] 0.6 Preserve existing slash command behavior unless explicitly corrected by result semantics.
- [x] 0.7 Preserve read-only research boundary.
- [x] 0.8 Do not mark complete without tests and validation evidence.

## 1. CLI modularisation

- [x] 1.1 Create modular CLI package or `cli_app` package if `cli.py` name collision prevents `cli/` package.
- [x] 1.2 Move Typer app creation to `cli_app/app.py` or `cli/app.py`.
- [x] 1.3 Move common env/logging helpers to `common.py`.
- [x] 1.4 Move sync commands to `sync.py`.
- [x] 1.5 Move build commands to `build.py`.
- [x] 1.6 Move score command to `score.py`.
- [x] 1.7 Move watchlist command to `watchlist.py`.
- [x] 1.8 Move TUI launch command to `tui.py`.
- [x] 1.9 Move outcome commands to `outcome.py`.
- [x] 1.10 Keep `vnalpha.cli:app` working.
- [x] 1.11 Add CLI compatibility tests.

## 2. Central policy package

- [x] 2.1 Add `vnalpha/policy/__init__.py`.
- [x] 2.2 Add `permissions.py` or re-export existing `ToolPermission` safely.
- [x] 2.3 Add `tool_policy.py` with central tool capability definitions.
- [x] 2.4 Add `command_policy.py` for command metadata or command permission mapping.
- [x] 2.5 Add `assistant_policy.py` for assistant/autonomous allowlist derivation.
- [x] 2.6 Add `safety_policy.py` for research-only boundary constants if useful.
- [x] 2.7 Ensure every local tool has a policy entry.
- [x] 2.8 Add tests for policy completeness.

## 3. Remove duplicated allowlists

- [x] 3.1 Refactor `assistant.executor` allowlist to derive from central policy.
- [x] 3.2 Refactor `assistant.planner` allowlist to derive from central policy.
- [x] 3.3 Refactor `tools.setup.TOOL_PERMISSIONS` to derive from central policy or assert equivalence.
- [x] 3.4 Refactor command registry permissions to align with central policy.
- [x] 3.5 Add tests proving planner/executor/tool permissions remain consistent.

## 4. Remove assistant autonomous `data.fetch`

- [x] 4.1 Mark `data.fetch` as mutating warehouse in policy.
- [x] 4.2 Set `allowed_for_assistant=false` for `data.fetch`.
- [x] 4.3 Set `allowed_for_autonomous_plan=false` for `data.fetch`.
- [x] 4.4 Remove `data.fetch` from assistant executor allowlist.
- [x] 4.5 Remove `data.fetch` from planner allowlist.
- [x] 4.6 Change `fetch_data` intent planning to refusal or explicit-command guidance.
- [x] 4.7 Keep deterministic `ensure_symbol_analysis_ready()` path for analysis tools.
- [x] 4.8 Add tests proving assistant cannot call `data.fetch`.
- [x] 4.9 Add tests proving `/explain` still auto-provisions through ensure-data.

## 5. TUI router refactor

- [x] 5.1 Add `vnalpha/tui/routing/__init__.py`.
- [x] 5.2 Add `routing/router.py`.
- [x] 5.3 Add `routing/command_path.py`.
- [x] 5.4 Add `routing/chat_path.py`.
- [x] 5.5 Add `routing/status_adapter.py`.
- [x] 5.6 Add `routing/lifecycle_hooks.py`.
- [x] 5.7 Add `routing/events.py`.
- [x] 5.8 Keep `vnalpha.tui.input_router.TuiInputRouter` import path working.
- [x] 5.9 Move command execution/rendering into command path.
- [x] 5.10 Move chat execution/rendering into chat path.
- [x] 5.11 Move status mapping into status adapter.
- [x] 5.12 Move audit event helpers into events module.
- [x] 5.13 Add tests for router delegation.

## 6. TUI layout boundary

- [x] 6.1 Add `vnalpha/tui/responsive_layout.py` skeleton or boundary if not already present.
- [x] 6.2 Add layout policy tests or placeholders for future TODO panel.
- [x] 6.3 Ensure default layout remains StatusBar + OutputStream + ComposerInput + FooterHint.
- [x] 6.4 Add mounted DOM tests where feasible.
- [x] 6.5 Preserve one Textual Input.
- [x] 6.6 Preserve no ContentSwitcher and no secondary ChatPanel.

## 7. Model routing boundary

- [x] 7.1 Add `vnalpha/model_routing/__init__.py`.
- [x] 7.2 Add `models.py` with `ModelProfile` and `ModelRouteDecision`.
- [x] 7.3 Add `config.py` with env-backed profile config skeleton.
- [x] 7.4 Add `policy.py` with deterministic default profile rules skeleton.
- [x] 7.5 Add `resolver.py` with profile-to-model resolution.
- [x] 7.6 Add `overrides.py` with session/workspace override skeleton.
- [x] 7.7 Add `observability.py` with model route event helpers.
- [x] 7.8 Add `integration.py` for gateway integration helpers.
- [x] 7.9 Update `assistant.gateway.LLMGatewayClient.chat()` signature to accept `task_type`, `model_profile`, and `route_metadata`.
- [x] 7.10 Preserve current `VNALPHA_LLM_MODEL` behavior as default.
- [x] 7.11 Add gateway compatibility tests.

## 8. Workspace context boundary

- [x] 8.1 Add `vnalpha/workspace_context/__init__.py`.
- [x] 8.2 Add minimal `models.py`.
- [x] 8.3 Add minimal `storage.py` boundary.
- [x] 8.4 Add minimal `lifecycle.py` boundary.
- [x] 8.5 Add minimal `integration.py` boundary.
- [x] 8.6 Do not implement full lifecycle unless separately scoped.
- [x] 8.7 Add import tests.

## 9. Data availability service split

- [x] 9.1 Add `data_availability/planner.py`.
- [x] 9.2 Add `data_availability/actions.py`.
- [x] 9.3 Add `data_availability/service.py`.
- [x] 9.4 Keep `ensure.py` as backward-compatible wrapper or thin orchestration layer.
- [x] 9.5 Separate check/plan/action/execute phases.
- [x] 9.6 Add `EnsureDataPlan` model if needed.
- [x] 9.7 Extend `EnsureDataResult` with freshness/lineage fields.
- [x] 9.8 Add planning-only tests.
- [x] 9.9 Add wrapper compatibility tests.

## 10. Command result semantics

- [x] 10.1 Add `CommandStatus` enum or constants.
- [x] 10.2 Add statuses or helper methods for `EMPTY_RESULT` and `PARTIAL`.
- [x] 10.3 Update `/explain` no-score path to avoid plain `SUCCESS`.
- [x] 10.4 Update `/compare` no-records path to avoid plain `SUCCESS`.
- [x] 10.5 Update renderer handling for new statuses.
- [x] 10.6 Update session status mapping.
- [x] 10.7 Add command status tests.

## 11. Remove stale phase coupling

- [x] 11.1 Remove or update Phase 5.8/5.9 wording from assistant executor comments.
- [x] 11.2 Remove or update Phase 5.8/5.9 wording from planner comments.
- [x] 11.3 Remove or update Phase wording from tools setup comments.
- [x] 11.4 Replace with capability-based language.
- [x] 11.5 Add grep-style regression test or docs check if feasible.

## 12. Architecture docs

- [x] 12.1 Add `vnalpha/docs/architecture.md`.
- [x] 12.2 Add `vnalpha/docs/package-boundaries.md`.
- [x] 12.3 Update `vnalpha/docs/tui-workspace.md` if TUI router paths change.
- [x] 12.4 Document target CLI tree.
- [x] 12.5 Document policy source of truth.
- [x] 12.6 Document assistant mutation boundary.
- [x] 12.7 Document model routing boundary.
- [x] 12.8 Document workspace context boundary.

## 13. Regression tests

- [x] 13.1 Add architecture boundary tests.
- [x] 13.2 Add CLI app compatibility tests.
- [x] 13.3 Add policy consistency tests.
- [x] 13.4 Add assistant no-`data.fetch` tests.
- [x] 13.5 Add TUI router import/delegation tests.
- [x] 13.6 Add command result status tests.
- [x] 13.7 Add gateway signature compatibility tests.
- [x] 13.8 Add package import tests for new boundaries.

## 14. Validation

- [x] 14.1 Run `make test-vnalpha`.
- [x] 14.2 Run `make lint-vnalpha`.
- [x] 14.3 Run `make verify-r4`.
- [x] 14.4 Run `openstock-verify --ci`.
- [x] 14.5 Add validation evidence for existing CLI command compatibility.
- [x] 14.6 Add validation evidence for policy centralisation.
- [x] 14.7 Add validation evidence that assistant cannot autonomously call `data.fetch`.
- [x] 14.8 Add validation evidence for TUI layout/router regression tests.

### Validation evidence

- `VNALPHA_WAREHOUSE_PATH=/tmp/opencode/vnalpha-architecture-gap-<pid>.duckdb make test-vnalpha` — exit 0. The isolated path avoids contending with the user's live TUI while exercising the same Make target.
- `make lint-vnalpha` — Ruff checks passed; all 312 files are format-clean.
- `make verify-r4` — exit 0; the complete R4 acceptance selection passed.
- `./packaging/scripts/openstock-verify --ci` — PASS: 16 OK, 1 existing systemd warning, 0 FAIL.
- CLI compatibility — `vnalpha.cli:app` and the historical `build_features_cmd`, `score`, `watchlist`, and `tui` imports are covered by CLI contract and end-to-end wiring tests.
- Policy centralisation — capability completeness, planner/executor consistency, and registry permission tests pass in the full suite.
- Assistant mutation boundary — planner and executor tests prove `data.fetch` is rejected for autonomous use while analysis still provisions through `ensure_symbol_analysis_ready()`.
- TUI regressions — legacy router imports, command/chat delegation, operational bypass, mounted layout, single-Input, and no-`ContentSwitcher`/secondary-`ChatPanel` tests pass in the full suite.
