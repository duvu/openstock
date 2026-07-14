# Issue #95 Context Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every deep-context readiness path return safe typed evidence, preserve policy evidence, and lock the contract with regression coverage.

**Architecture:** Parse context requirements at the public request boundary; execute date resolution, core readiness, context evaluation/build/reload, and rendering through one failure-to-result boundary. Context artifacts carry structured evidence and issue-specific repair steps; the deep tool separates required from optional unavailable context.

**Tech Stack:** Python 3.10, DuckDB, pytest, Typer, existing observability audit events, OpenSpec.

---

### Task 1: Typed request parsing and structured lifecycle failures

**Files:**
- Modify: `vnalpha/src/vnalpha/data_availability/deep_readiness_models.py`
- Modify: `vnalpha/src/vnalpha/data_availability/deep_readiness_service.py`
- Modify: `vnalpha/src/vnalpha/assistant/executor.py`
- Test: `vnalpha/tests/test_context_readiness.py`

- [ ] Write failing tests for whitespace/case-normalized requirement values, unknown values, date failure, context-evaluation failure, and builder failure.
- [ ] Run `cd vnalpha && uv run pytest tests/test_context_readiness.py -q`; verify each test fails due to direct enum conversion or an escaping exception.
- [ ] Add a public parser/outcome and move all readiness stages into the service's typed failure boundary; preserve sanitized public messages and correlation ID.
- [ ] Run the focused tests; verify all pass.

### Task 2: Evidence, root-cause remediation, and optional output

**Files:**
- Modify: `vnalpha/src/vnalpha/data_availability/deep_readiness_models.py`
- Modify: `vnalpha/src/vnalpha/data_availability/deep_context_artifacts.py`
- Modify: `vnalpha/src/vnalpha/data_availability/deep_context_readiness.py`
- Modify: `vnalpha/src/vnalpha/tools/research_intelligence.py`
- Test: `vnalpha/tests/test_context_readiness.py`
- Test: `vnalpha/tests/test_phase3_artifact_references.py`

- [ ] Write failing tests requiring market breadth, sector coverage/metadata, alignment rank/score/rotation/lineage evidence, issue-specific remediation, and `optional_missing_data` for optional market and sector requests.
- [ ] Run only those tests; verify current generic commands and `missing_data` behavior fail the assertions.
- [ ] Add immutable typed context evidence to artifacts and map each `ContextIssue` to only presently registered executable repair steps. Keep optional unavailable artifacts visible, non-blocking, and out of `missing_data`.
- [ ] Run focused context and tool-output tests; verify all pass.

### Task 3: Builder lifecycle audit and legacy compatibility

**Files:**
- Modify: `vnalpha/src/vnalpha/data_availability/deep_readiness_audit.py`
- Modify: `vnalpha/src/vnalpha/data_availability/deep_context_readiness.py`
- Modify: `vnalpha/src/vnalpha/warehouse/repositories.py`
- Test: `vnalpha/tests/test_context_readiness.py`
- Test: `vnalpha/tests/test_deep_analysis_readiness.py`

- [ ] Write failing tests for cache evaluation/build start/build success/build failure/revalidation event order and one correlation ID, plus null/malformed lineage, missing methodology, and null generated metadata rows.
- [ ] Run the focused tests; verify current events omit the lifecycle and null generated metadata raises `TypeError`.
- [ ] Emit lifecycle events around each bounded builder and deserialize malformed legacy rows as typed unusable artifacts rather than exceptions.
- [ ] Run focused tests; verify all pass.

### Task 4: User-facing command/tool integration

**Files:**
- Modify: `vnalpha/src/vnalpha/commands/handlers/analyze.py`
- Modify: `vnalpha/src/vnalpha/assistant/executor.py`
- Test: `vnalpha/tests/test_context_readiness.py`
- Test: `vnalpha/tests/test_deep_analysis_readiness.py`

- [ ] Write failing command and assistant tests for normalized context values and structured invalid outcomes.
- [ ] Run them; verify malformed input cannot escape as a raw conversion exception.
- [ ] Wire only public parsed outcomes through the existing command/assistant boundary and render readiness evidence without internal exception details.
- [ ] Run focused command/assistant tests; verify all pass.

### Task 5: Evidence and validation

**Files:**
- Modify: `openspec/changes/deep-symbol-analysis-engine/tasks.md`
- Modify: `openspec/changes/deep-symbol-analysis-engine/validation.md`

- [ ] Run `make lint-vnalpha`, `make test-vnalpha`, `make verify-r4`, `packaging/scripts/openstock-verify --ci`, and `openspec validate deep-symbol-analysis-engine --strict`.
- [ ] Update only tasks supported by recorded commands and exact outcomes; do not claim GitHub Actions execution from a local run.
- [ ] Check `git diff --check` and modified-file LOC; run changed-file no-excuse rules where available.
