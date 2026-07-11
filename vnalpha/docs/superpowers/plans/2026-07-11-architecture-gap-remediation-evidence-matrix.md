# Architecture Gap Remediation Evidence Matrix

This matrix reconciles the OpenSpec task list with the active candidate before
any checkbox is changed. `verified` requires a passing command recorded in this
session; `pending validation` identifies an existing implementation and its
intended proof; `spec drift` identifies a literal task that conflicts with a
preserved public compatibility contract. The task file contains 111
checkboxes, matching the OpenSpec CLI progress output.

## 0. Governance

| Task | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 0.1 | pending validation | Change proposal/design boundaries | Focused and final validation; no write-capable research behavior tests regress |
| 0.2 | pending validation | `pyproject.toml`, `src/vnalpha/cli.py` | `tests/test_cli_contract.py` |
| 0.3 | pending validation | `tui/app.py`, `tui/routing/` | `tests/test_tui_layout.py tests/test_tui_pilot.py` |
| 0.4 | pending validation | No matching runtime commands in CLI/registry | CLI and tool-policy tests |
| 0.5 | pending validation | Test suite and validation tasks | Focused plus mandated validation commands |
| 0.6 | pending validation | Compatibility shims and existing contracts | Focused regression suites |

## 1. CLI entrypoint

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 1.1-1.10 | spec drift | Modular commands live in `src/vnalpha/cli_app/`, while a sibling `cli/` package would conflict with `cli.py` import compatibility | OpenSpec-owner acceptance of `cli_app/` equivalence plus CLI contract tests |
| 1.11 | pending validation | `src/vnalpha/cli.py` re-exports from `cli_app` | `tests/test_cli_contract.py` |
| 1.12 | pending validation | `tests/test_cli_contract.py`, `test_cli.py`, `test_ask_cli.py` | CLI focused suite |

## 2. Central policy package

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 2.1-2.6 | pending validation | `policy/__init__.py`, `permissions.py`, `tool_policy.py`, `assistant_policy.py`, `command_policy.py`, `safety_policy.py` | `test_policy_capabilities.py test_tool_policy.py` |
| 2.7-2.10 | pending validation | `ToolCapability`, `TOOL_CAPABILITIES`, derived assistant and permission mappings in policy | Policy focused suite |
| 2.11 | pending validation | `test_policy_capabilities.py`, `test_tool_policy.py`, `test_command_safety.py` | Policy focused suite |

## 3. Tools consume policy

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 3.1-3.3 | pending validation | `tools/setup.py` derives permissions from policy; registry metadata maps all registered names | `test_tool_policy.py test_policy_capabilities.py` |
| 3.4-3.5 | pending validation | Policy/registry coverage tests | Same focused suite |

## 4. Assistant policy migration

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 4.1-4.3 | pending validation | Planner and executor use `assistant.tool_policy.assert_safe_tool`, with policy-derived allowlists | `test_executor_and_policy.py test_intent_and_planner.py` |
| 4.4-4.8 | pending validation | `data.fetch` is manual-only; `fetch_data` refuses; forged executor steps reject before execution | Same focused suite and direct allowlist assertion |

## 5. TUI routing

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 5.1-5.7 | pending validation | `tui/routing/{__init__,router,command_path,chat_path,status_adapter,lifecycle_hooks,events}.py` | `test_tui_routing.py test_tui_workspace.py` |
| 5.8 | pending validation | `tui/input_router.py` direct re-export | Router identity test |
| 5.9-5.12 | pending validation | Command/chat paths, status adapter, lifecycle hook modules | Routing and workspace suites |
| 5.13 | pending validation | Existing routing, pilot, operational-router, workspace tests | TUI focused suite |

## 6. Command status semantics

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 6.1-6.2 | spec drift | Shipped compatibility member is `CommandStatus.EMPTY_RESULT`, not `EMPTY`; renderers support that member | `tests/test_command_status.py`; owner acceptance that `EMPTY_RESULT` fulfills empty semantics |
| 6.3 | pending validation | `PARTIAL` and renderer color mapping exist | `tests/test_command_status.py` |
| 6.4-6.5 | pending validation | `StatusAdapter` module exists; behavior must be confirmed against command outcomes | TUI runtime-status and command-status suites |
| 6.6-6.7 | pending validation | Explain/compare emit `EMPTY_RESULT` or `PARTIAL` as appropriate | Command-status/handler tests |
| 6.8-6.9 | pending validation | Scan/filter behavior must be located and tested | Command-handler focused suite |
| 6.10 | pending validation | `tests/test_command_status.py` | Command-status suite |

## 7. Data availability

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 7.1-7.2, 7.4 | pending validation | `data_availability/{planner,actions,service}.py` | Data-availability focused suite |
| 7.3, 7.7 | spec drift | `service.py` owns ordered action execution; no standalone `executor.py` | Service-split tests and owner decision whether extraction is acceptance-critical |
| 7.5-7.10 | pending validation | `ensure.py` facade retains injection signature; observability/result contracts live in service/models | Ensure, integration, lock/observability suites |
| 7.11-7.13 | pending validation | Checks, ensure, service-split, integration tests cover conditions, plans, injected fakes | Data-availability focused suite |

## 8-9. Runtime package boundaries

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 8.1-8.4 | pending validation | `model_routing/` runtime package and gateway boundaries | `tests/test_model_routing.py tests/test_architecture_phase_coupling.py` |
| 9.1-9.4 | pending validation | `workspace_context/` package integrates through lifecycle hooks rather than router | `tests/workspace_context tests/test_tui_workspace_context_lifecycle.py` |

## 10. Architecture tests

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 10.1 | pending validation | Existing architecture-phase coupling test; dedicated boundaries test is not yet confirmed | Locate/execute architecture boundary test; add only if behavior gap is proven |
| 10.2-10.5 | pending validation | CLI/policy suites cover these observable contracts | CLI and policy focused suites |
| 10.6-10.8 | pending validation | TUI layout/routing suites and package modules | TUI focused suite |

## 11. Documentation

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 11.1-11.8 | pending validation | `docs/architecture.md`, `docs/package-boundaries.md`, `docs/tui-workspace.md` | `test_architecture_phase_coupling.py` and manual source-to-doc review |

## 12. Validation

| Tasks | Disposition | Candidate evidence | Required proof |
| --- | --- | --- | --- |
| 12.1-12.4 | pending validation | Repository Make targets and `openstock-verify` | Run exact mandated commands last |
| 12.5-12.9 | pending validation | This matrix plus focused subsystem outputs | Record passing focused commands before checkbox reconciliation |

## Reconciliation rules

1. Do not check a task until its required proof passes in this session.
2. Do not create `cli/` or rename `EMPTY_RESULT`; both require an approved
   OpenSpec wording correction because the literal task conflicts with public
   compatibility.
3. Do not extract `data_availability/executor.py` unless a failing behavior
   contract proves that the service-owned executor boundary is insufficient.
