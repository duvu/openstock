# Queue Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the completed durable SQLite queue, then complete #324.4 so the sequential worker safely observes stop/cancellation only at durable stage boundaries.

**Architecture:** Start from `agent/issue-325-queue-client`, whose queue repository and most worker contract have passed their owning tests. Keep the public worker and CLI API stable, split the oversized worker test into private scenario modules, and make stage execution explicitly boundary-aware: no asynchronous interruption of DuckDB/provider work; a request to stop prevents a subsequent stage or job claim.

**Tech Stack:** Python 3.10, DuckDB, SQLite, pytest, Typer, OpenSpec.

---

### Task 1: Integrate the verified queue foundation

**Files:**

- Modify: all files already committed on `agent/issue-325-queue-client`.
- Test: `vnalpha/tests/test_provisioning_queue_goals.py`
- Test: `vnalpha/tests/test_provisioning_queue_repository.py`
- Test: `vnalpha/tests/test_provisioning_queue_worker.py`

- [ ] Merge `agent/issue-325-queue-client` into `codex/queue-foundation` without changing its history.

  ```bash
  git merge --no-ff agent/issue-325-queue-client
  ```

- [ ] Run each existing owning contract once from the repository root.

  ```bash
  make test-loop TEST=tests/test_provisioning_queue_goals.py::test_provisioning_goal_contract
  make test-loop TEST=tests/test_provisioning_queue_repository.py::test_durable_provisioning_queue_contract
  make test-loop TEST=tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract
  ```

- [ ] Confirm OpenSpec task 3.1–3.5 and 4.1–4.3/4.5 are evidenced by the merged implementation; leave 4.4 unchecked until its observable contract passes.

### Task 2: Make worker execution stage-boundary aware

**Files:**

- Modify: `vnalpha/src/vnalpha/provisioning_queue/worker.py`
- Modify: `vnalpha/src/vnalpha/provisioning_queue/_worker_runtime.py`
- Modify: `vnalpha/src/vnalpha/provisioning_queue/handlers.py`
- Create: `vnalpha/src/vnalpha/provisioning_queue/_worker_execution.py`
- Test: `vnalpha/tests/test_provisioning_queue_worker.py`
- Create: `vnalpha/tests/provisioning_queue_worker_contract_support.py`
- Create: `vnalpha/tests/provisioning_queue_worker_scenarios.py`

- [ ] Move private handler/stage orchestration out of `worker.py` so that file retains the public `WorkerSettings`, `ProvisioningWorker`, configuration validation, and compatibility exports under the 250 pure-LOC limit.

  ```python
  def execute_stage_sequence(job: ProvisioningJob, handler: ProvisioningGoalHandler) -> HandlerResult:
      for stage in handler.stages(job.goal):
          if stop_requested() or cancellation_requested(job):
              return HandlerResult(False, "CANCELLED_AT_SAFE_BOUNDARY")
          with lease_heartbeat(job):
              with warehouse_boundary(stage) as connection:
                  result = stage.execute(connection)
          if stage_elapsed() > stage_timeout_seconds:
              return HandlerResult(False, "STAGE_TIMEOUT")
      return result
  ```

- [ ] Extend the handler protocol with finite, statically defined stages. Each stage owns one safe warehouse transaction boundary; no dynamic payload-selected execution is introduced. The existing current-symbol path remains one terminal business operation, but cancellation/stop is checked before every declared stage and no next stage begins after either flag is observed.

- [ ] Preserve `request_stop()` and `shutdown_signals()` semantics: a signal only sets the stop event; an in-flight stage exits at its natural commit/rollback boundary; the worker does not claim the next job. A local stop never reports an invented terminal success and leaves an unfinished job recoverable through its lease/replan path.

- [ ] Keep heartbeat active for the complete stage, check timeout only after its safe boundary, and do not execute a following stage after a timeout or lost lease.

### Task 3: Consolidate the authoritative worker contract

**Files:**

- Modify: `vnalpha/tests/test_provisioning_queue_worker.py`
- Create: `vnalpha/tests/provisioning_queue_worker_contract_support.py`
- Create: `vnalpha/tests/provisioning_queue_worker_scenarios.py`
- Modify: `vnalpha/tests/suites/authoritative.toml` only if the existing path changes; retain one exact node.

- [ ] Keep `test_sequential_provisioning_worker_contract` as the sole collected test function and have it call private `assert_*` scenario helpers. Do not introduce a second `test_*` node.

  ```python
  def test_sequential_provisioning_worker_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
      assert_restart_reuses_committed_effect(tmp_path)
      assert_cancellation_and_stop_observe_safe_boundaries(tmp_path)
      assert_lease_timeout_and_exclusive_worker_semantics(tmp_path)
      assert_worker_cli_processes_one_job(tmp_path, monkeypatch)
  ```

- [ ] Strengthen the existing contract with Event/barrier-driven scenarios, not sleeps: stop during stage one leaves job two queued; cancellation after stage one prevents stage two; signal context restores prior handlers; timeout maintains the lease during a stage and preserves at-least-once replan behavior.

- [ ] Run the owning test once and confirm collection is still one node.

  ```bash
  make test-loop TEST=tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract
  cd vnalpha && pytest --collect-only -q tests/test_provisioning_queue_worker.py
  ```

### Task 4: Record completion evidence and publish the queue slice

**Files:**

- Modify: `openspec/changes/queue-backed-cache-first-current-symbol-provisioning/tasks.md`
- Modify: `openspec/active-changes.yaml`

- [ ] After validation, mark task 4.4 complete with exact commit/test evidence; do not mark later queue, application, maintenance, packaging, or live-soak tasks complete.
- [ ] Run focused Ruff and strict OpenSpec validation from the frozen commit.

  ```bash
  cd vnalpha && uv run ruff check src/vnalpha/provisioning_queue tests/test_provisioning_queue_worker.py
  cd vnalpha && uv run ruff format --check src/vnalpha/provisioning_queue tests/test_provisioning_queue_worker.py
  openspec validate queue-backed-cache-first-current-symbol-provisioning --strict
  ```

- [ ] Commit the integrated foundation and #324.4 completion as intentional, reversible commits; push the branch, open a PR, and close #323 only after its PR is merged into `main`. Keep #324 open unless all its acceptance criteria are evidenced.

**Verification and closure evidence:**

```text
contract_id: provisioning-queue-worker-sequential-lifecycle-contract
authoritative_test: vnalpha/tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract
tests_removed_or_merged: worker scenarios moved behind the same authoritative test node
net_test_count_change: 0
net_test_LOC_change: calculated from `git diff --numstat origin/main...HEAD` before the PR is opened
validation_command: make test-loop TEST=tests/test_provisioning_queue_worker.py::test_sequential_provisioning_worker_contract
```
