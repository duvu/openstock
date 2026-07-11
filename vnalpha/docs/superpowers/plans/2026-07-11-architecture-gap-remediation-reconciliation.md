# Architecture Gap Remediation Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the 111 OpenSpec tasks for `architecture-gap-remediation` against the active `vnalpha` candidate, make only evidence-proven compatibility repairs, and mark only verified work complete.

**Architecture:** The active worktree already implements the intended boundaries through `cli_app`, `policy`, `tui/routing`, and `data_availability` modules. Preserve that working architecture and its public contracts; treat literal target-tree differences as specification drift unless a behavior-level acceptance test proves an actual gap.

**Tech Stack:** Python 3.10+, Typer, Textual, pytest, DuckDB, Make, OpenSpec.

---

## Protected Contracts

- `pyproject.toml` continues to expose `vnalpha = "vnalpha.cli:app"`.
- `src/vnalpha/cli.py` remains an import-compatible shim; do not create a sibling `vnalpha/cli/` package that conflicts with it.
- Keep `CommandStatus.EMPTY_RESULT`; do not rename it to `EMPTY`.
- Keep `vnalpha.tui.input_router.TuiInputRouter` as the identical routing class, not a subclass or wrapper.
- Keep one default `ComposerInput`, one underlying Textual `Input`, and one `OutputStream`.
- Keep `data.fetch` in the local registry for explicit/manual use, but out of assistant and autonomous-plan allowlists.
- Keep every keyword-only injection hook on `ensure_symbol_analysis_ready()` and preserve `EnsureDataResult.to_panel_dict()`.
- Do not reset, stash, checkout, or stage unrelated dirty changes.

## File Map

| Path | Responsibility during reconciliation |
|---|---|
| `openspec/changes/architecture-gap-remediation/tasks.md` | Evidence-backed task completion record; update only after final validation. |
| `src/vnalpha/cli.py`, `src/vnalpha/cli_app/` | CLI compatibility implementation and modular command groups. |
| `src/vnalpha/policy/`, `src/vnalpha/tools/setup.py`, `src/vnalpha/assistant/` | Central capability metadata and manual-only data-fetch safety boundary. |
| `src/vnalpha/tui/input_router.py`, `src/vnalpha/tui/routing/`, `src/vnalpha/tui/app.py` | Router identity and mounted layout contracts. |
| `src/vnalpha/commands/models.py`, `src/vnalpha/commands/renderers/` | Command-result status compatibility. |
| `src/vnalpha/data_availability/` | Public availability facade and service/planner/action boundaries. |
| `tests/test_architecture_boundaries.py` | Create or extend only when a behavior boundary lacks durable regression coverage. |
| `docs/architecture.md`, `docs/package-boundaries.md`, `docs/tui-workspace.md` | Describe the accepted, validated package tree rather than obsolete literal paths. |

## Task 1: Freeze the Candidate Baseline

**Files:**
- Modify: none
- Test: none

- [ ] **Step 1: Record repository ownership and dirty-state evidence without writing files.**

  Run from `/home/beou/IdeaProjects/openstock`:

  ```bash
  git rev-parse --show-toplevel
  git status --short
  git diff --check
  git diff --name-only
  git log --oneline -20
  ```

  Expected: the root is `/home/beou/IdeaProjects/openstock`; the output identifies pre-existing workspace/OpenSpec archival changes and overlapping `vnalpha` changes.

- [ ] **Step 2: Protect overlapping files before any modification.**

  Before touching an overlapping file, run:

  ```bash
  git diff -- "vnalpha/src/vnalpha/policy/tool_policy.py"
  git diff -- "vnalpha/src/vnalpha/tools/setup.py"
  git diff -- "vnalpha/src/vnalpha/assistant/planner.py"
  git diff -- "vnalpha/src/vnalpha/tui/routing/lifecycle_hooks.py"
  ```

  Expected: unrelated existing hunks are visible and remain unchanged by reconciliation work.

## Task 2: Build the OpenSpec Evidence Matrix

**Files:**
- Modify: none during classification
- Test: focused existing tests named below

- [ ] **Step 1: Classify every task in `tasks.md` as implemented, implemented-but-unproven, specification drift, or genuine gap.**

  Use one row per OpenSpec ID with: requirement/scenario, source path/symbol, focused test command, disposition, and rationale. Maintain the matrix in the execution transcript or review artifact until its claims are validated.

  Seed classifications with these known facts:

  ```text
  CLI: cli.py shim + cli_app/ implementation; literal cli/ target is specification drift.
  Policy: policy.tool_policy drives permissions; assistant policy excludes data.fetch.
  TUI: input_router re-exports routing.router.TuiInputRouter; routing modules already exist.
  Status: EMPTY_RESULT is the supported, tested empty semantic.
  Availability: checks/planner/actions/service and public ensure facade already exist.
  Future boundaries: model_routing and workspace_context packages already exist.
  ```

- [ ] **Step 2: Flag, do not immediately repair, the two structural discrepancies.**

  ```text
  1. The OpenSpec requests cli/ while the compatible implementation uses cli.py plus cli_app/.
  2. The OpenSpec requests data_availability/executor.py while service.py currently owns execution orchestration.
  ```

  Expected: both are evaluated by behavior and accepted documentation rather than resolved with duplicate packages.

## Task 3: Validate the Existing Contracts

**Files:**
- Modify: none
- Test: existing CLI, policy, status, availability, TUI, and package-boundary suites

- [ ] **Step 1: Run CLI and assistant-policy regression tests.**

  ```bash
  cd /home/beou/IdeaProjects/openstock/vnalpha
  .venv/bin/python -m pytest \
    tests/test_cli_contract.py \
    tests/test_tool_policy.py \
    tests/test_policy_capabilities.py \
    tests/test_executor_and_policy.py -q
  ```

  Expected: all tests pass; the console shim, registry-policy alignment, planner refusal, and executor rejection remain intact.

- [ ] **Step 2: Assert manual-only `data.fetch` directly.**

  ```bash
  .venv/bin/python -c "from vnalpha.policy.assistant_policy import ASSISTANT_TOOL_NAMES, AUTONOMOUS_PLAN_TOOL_NAMES; from vnalpha.tools.setup import TOOL_PERMISSIONS; assert 'data.fetch' not in ASSISTANT_TOOL_NAMES; assert 'data.fetch' not in AUTONOMOUS_PLAN_TOOL_NAMES; assert 'data.fetch' in TOOL_PERMISSIONS"
  ```

  Expected: exit status 0.

- [ ] **Step 3: Run command-status regression tests.**

  ```bash
  .venv/bin/python -m pytest tests/test_command_status.py tests/test_command_handlers.py -q
  ```

  Expected: `EMPTY_RESULT` and `PARTIAL` render correctly, and no-score behavior is not reported as plain success.

- [ ] **Step 4: Run public availability API and split-service tests.**

  ```bash
  .venv/bin/python -m pytest \
    tests/test_data_availability_checks.py \
    tests/test_data_availability_ensure.py \
    tests/test_data_availability_service_split.py \
    tests/test_data_availability_integration.py \
    tests/test_data_availability_lock_and_observability.py -q
  ```

  Expected: the facade, injection hooks, lock behavior, observability events, and panel-compatible result pass.

- [ ] **Step 5: Run mounted TUI routing and layout checks.**

  ```bash
  .venv/bin/python -m pytest \
    tests/test_tui_routing.py \
    tests/test_tui_layout.py \
    tests/test_tui_pilot.py \
    tests/test_tui_workspace.py \
    tests/test_tui_todo_panel.py \
    tests/test_tui_control_plane.py -q
  ```

  Expected: router alias identity holds; default UI has exactly one input, composer, output stream, and status bar; no default dashboard widgets appear.

- [ ] **Step 6: Validate package and architecture documentation boundaries.**

  ```bash
  .venv/bin/python -m pytest \
    tests/test_model_routing.py \
    tests/workspace_context \
    tests/test_architecture_phase_coupling.py -q
  ```

  Expected: runtime boundary packages and documented dependency direction import and test cleanly.

## Task 4: Repair Only a Proven Gap (TDD)

**Files:**
- Modify: only the source/test pair identified by a failed Task 3 acceptance contract
- Test: exact failed node plus owning subsystem suite

- [ ] **Step 1: Add a focused failing test for a matrix row classified as a genuine gap.**

  Example for a missing TUI command-status projection in `tests/test_tui_routing.py`:

  ```python
  def test_status_adapter_maps_empty_result_to_ready_message() -> None:
      adapter = StatusAdapter()
      status = adapter.from_command_status(CommandStatus.EMPTY_RESULT)
      assert status.kind is RuntimeStatusKind.READY
  ```

  Run the exact test node and confirm it fails for the missing behavior, not environment setup:

  ```bash
  .venv/bin/python -m pytest tests/test_tui_routing.py::test_status_adapter_maps_empty_result_to_ready_message -q
  ```

- [ ] **Step 2: Make the smallest typed implementation change.**

  Preserve the protected contracts. Do not introduce a `cli/` package, rename `EMPTY_RESULT`, wrap `TuiInputRouter`, remove local `data.fetch`, or change availability-facade keywords.

- [ ] **Step 3: Prove the fix and subsystem behavior.**

  ```bash
  .venv/bin/python -m pytest <exact-failing-node> <owning-subsystem-tests> -q
  ```

  Expected: the new test and all owning subsystem tests pass.

- [ ] **Step 4: If no behavior-level test fails, make no source change.**

  Expected: retain the task as `implemented` rather than manufacturing a structural change to satisfy a stale file path.

## Task 5: Add Durable Boundary Tests and Accurate Documentation

**Files:**
- Create or modify: `tests/test_architecture_boundaries.py`
- Modify only if the matrix proves a docs gap: `docs/architecture.md`, `docs/package-boundaries.md`, `docs/tui-workspace.md`

- [ ] **Step 1: Add behavior-first architecture assertions where equivalent coverage is missing.**

  Required assertions:

  ```python
  from vnalpha.cli import app
  from vnalpha.policy.assistant_policy import ASSISTANT_TOOL_NAMES
  from vnalpha.tools.setup import TOOL_PERMISSIONS

  def test_cli_shim_imports_root_app() -> None:
      assert app is not None

  def test_data_fetch_is_manual_only() -> None:
      assert "data.fetch" in TOOL_PERMISSIONS
      assert "data.fetch" not in ASSISTANT_TOOL_NAMES
  ```

  Extend with planner/executor rejection, router alias identity, and package import checks only where existing test suites do not already cover them.

- [ ] **Step 2: Document the accepted implementation tree.**

  The documentation must state:

  ```text
  cli.py is the console-script compatibility shim and cli_app/ contains the modular implementation.
  Policy modules are the source of truth for registry permissions and assistant eligibility.
  data.fetch is manual-only; readiness is deterministic for assistant analysis tools.
  EMPTY_RESULT is the compatibility value for valid empty command results.
  TUI routing is delegated through routing paths/adapters while input_router preserves import compatibility.
  Availability flows through checks, planning, action dispatch, service orchestration, and the public facade.
  ```

- [ ] **Step 3: Run durable architecture checks.**

  ```bash
  .venv/bin/python -m pytest \
    tests/test_architecture_boundaries.py \
    tests/test_cli_contract.py \
    tests/test_tool_policy.py \
    tests/test_command_status.py \
    tests/test_tui_pilot.py \
    tests/test_data_availability_service_split.py -q
  ```

  Expected: all selected tests pass.

## Task 6: Reconcile OpenSpec Checkboxes

**Files:**
- Modify: `openspec/changes/architecture-gap-remediation/tasks.md`
- Test: every command linked in the evidence matrix

- [ ] **Step 1: Check only rows with source evidence and a passing behavior/import/validation command.**

  Use this evidence rule for every checkbox:

  ```text
  Task ID + requirement/scenario + source/doc path + passing test command + disposition rationale.
  ```

- [ ] **Step 2: Preserve real gaps as unchecked.**

  Do not check a task whose test failed, was skipped for missing dependencies, lacks direct evidence, or depends on an OpenSpec-owner decision.

- [ ] **Step 3: Record accepted specification drift rather than duplicating packages.**

  If validated behavior confirms current equivalents, update the OpenSpec task wording or supporting documentation to recognize `cli_app/` and service-owned availability execution. Do this only after explicit artifact-owner acceptance.

## Task 7: Final Validation and Selective Commit Preparation

**Files:**
- Modify: none during validation
- Test: required Make and verification commands

- [ ] **Step 1: Run the required validation suite from the OpenStock root.**

  ```bash
  cd /home/beou/IdeaProjects/openstock
  make test-vnalpha
  make lint-vnalpha
  make verify-r4
  openstock-verify --ci
  ```

  Expected: each command exits 0. If a command fails, capture its output, identify whether it is pre-existing or caused by the reconciliation, and repair only a reconciliation-caused defect.

- [ ] **Step 2: Confirm the candidate has no introduced whitespace error and no accidental scope expansion.**

  ```bash
  git diff --check
  git status --short
  ```

- [ ] **Step 3: Commit only with explicit user authorization.**

  When authorized, inspect and stage explicit paths only:

  ```bash
  git diff --cached --check
  git diff --cached --name-only
  git diff --cached
  git log --oneline -10
  ```

  Never use `git add .`; do not absorb pre-existing workspace artifacts, archived OpenSpec moves, or unrelated market-context work.

## Plan Self-Review

- **Spec coverage:** All OpenSpec sections are represented by baseline, matrix, focused contract validation, conditional TDD, durable tests/docs, checkbox reconciliation, and final validation.
- **Compatibility:** The plan explicitly preserves the CLI entry point, `EMPTY_RESULT`, TUI alias/layout, manual-only `data.fetch`, and data-availability facade.
- **Scope:** No task directs a wholesale refactor; source edits occur only after a failing acceptance test proves a genuine gap.
- **Ambiguities:** `cli_app/` versus `cli/` and service-owned execution versus `executor.py` are explicitly treated as approval-gated specification drift.
