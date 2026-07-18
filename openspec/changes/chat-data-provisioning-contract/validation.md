# Validation Ledger

PR #168 merged the issue #163 implementation with required CI green. Current
follow-on validation for issue #175 covers nullable, malformed, duplicate,
empty, oversized, and service-unavailable remediation inputs. The shared
operation returns typed failure without exposing raw provider exceptions and
bounds remediation to eight items, 512 characters per item, and 2,048 total
characters.

| Command | Result |
|---|---|
| `cd vnalpha && uv run pytest -q tests/test_issue_163_chat_provisioning.py` | `18 passed` |
| `openspec validate chat-data-provisioning-contract --strict` | valid |

Exact-candidate installed-host acceptance remains owned by #162/#181 and is not
inferred from these focused tests.

## Issue #228 lifecycle and correlation regression - 2026-07-18

Implementation commit `b081cff180aa6b09b4f8b248c407dd20e9e2a316` restores
one exact correlation ID per accepted turn and truthful provisioning/tool stage
transitions. Failed tools cannot emit `SUCCESS` or `SYNTHESIZING`; successful
prepared turns synthesize only after all tool steps complete.

| Check | Outcome | Evidence |
|---|---|---|
| Focused lifecycle regressions | Passed | Five red/green selectors covering supplied IDs, per-turn uniqueness, successful ordering, and failed provisioning/tool terminal paths exited `0`. |
| Chat and routing regression surface | Passed | `tests/test_issue_163_chat_provisioning.py`, `tests/test_staged_response.py`, `tests/test_tui_routing.py`, `tests/test_chat_controller.py`, `tests/test_r4_trace.py`, `tests/test_plan_approval.py`, and `tests/test_observability.py` completed without failures in the affected-surface run. |
| R4 acceptance | Passed | `make verify-r4` completed at `100%` with exit code `0`. |
| Full vnalpha suite | Passed | `cd vnalpha && uv run --extra dev pytest -q` completed at `100%` with exit code `0` after the final fixture correction. |
| Installed-package vertical | Passed | `PIP_INDEX_URL=https://pypi.org/simple make verify-vnalpha-package` passed `59/59`, including fixture-contract and runtime-replay evaluation from the bundled application wheel. |
| Manual lifecycle smoke | Passed | Supplied correlation remained `turn-123`, generated turn IDs differed, successful prepared execution ordered tools before synthesis/final, and failed execution emitted neither synthesis nor success. |

## Issue #230 actionable chat tool failure boundary - 2026-07-18

The prepared natural-language boundary now presents assistant-layer
`ToolExecutionError` as one sanitized, bounded `[TOOL FAILED]` message and one
`tool_failed` transcript row. The public bound preserves the leading readiness
reason and the actionable remediation/correlation suffix. Known assistant input
and plan validation remain `validation_error`; unexpected exceptions retain the
fixed generic retry text and `error` transcript type. Issue #228 stage and tool
callbacks were not changed.

| Check | Outcome | Evidence |
|---|---|---|
| Red/green boundary regressions | Passed | Before implementation, `tests/test_issue_230_chat_tool_failures.py` plus `tests/test_chat_errors.py` had five expected failures: typed tool and validation errors reached the generic branch, public tool text was not bounded/sanitized, and `TOOL_FAILED` mapped to `tool_trace_event`. The final focused run passed all 26 tests. A separate oversized-reason regression failed before the head/tail bound and passed afterward while retaining remediation and correlation. |
| Affected chat/provisioning/lifecycle surface | Passed | `cd vnalpha && uv run --extra dev pytest -q tests/test_issue_230_chat_tool_failures.py tests/test_issue_163_chat_provisioning.py tests/test_assistant_lifecycle_hardening.py tests/test_staged_response.py tests/test_chat_controller.py tests/test_tui_routing.py tests/test_r4_trace.py tests/test_plan_approval.py tests/test_observability.py tests/test_chat_errors.py` completed at `100%`, exit `0`. |
| Manual controller/repository/tool lifecycle | Passed | Public `ChatController.handle_turn("Phân tích FPT", correlation_id="turn-correlation-230")` used the real `AssistantApp`, executor, registry, `data.ensure_current_symbol`, trace callbacks and migrated in-memory DuckDB, replacing only the unavailable LLM route and readiness source. It emitted one actionable `[TOOL FAILED]` message and one `tool_failed` transcript row; trace rows stayed `tool_trace_event`, the provisioning tool and assistant session ended `FAILED`, and no analysis, synthesis, success or generic retry was emitted. |
| Full vnalpha suite | Passed | `cd vnalpha && uv run --extra dev pytest -q` completed at `100%`, exit `0`, after the final public-bound implementation. The worktree environment required installing `pip` into its generated `.venv` so the existing package-resource subprocess tests could invoke `.venv/bin/python -m pip`; the affected selector then passed 3 tests before the full rerun. |
| R4 acceptance | Passed | `make verify-r4` completed 81 selected permission/session/trace/clear/persistence tests at `100%`, exit `0`. |
| Lint and formatting | Passed | `make lint-vnalpha` reported all checks passed and 694 files already formatted. Changed Python files had no language-server diagnostics. |
| Installed-package vertical | Passed | `PIP_INDEX_URL=https://pypi.org/simple make verify-vnalpha-package` built `/tmp/openstock-hardening-deb/vnalpha_0.1.0_amd64.deb` and passed 59/59 checks, including fixture-contract and runtime-replay evaluations from the bundled application wheel. Optional `shellcheck` was skipped because it is not installed. |
| Research evaluations | Passed | `make eval-research-answers` passed 5/5 evaluated cases with zero failures; `make eval-research-runtime` passed 22/22 runtime-replay cases with zero failures. |
| OpenSpec | Passed | `openspec validate chat-data-provisioning-contract --strict` reported the change valid. `python -m pytest -q scripts/tests/test_check_openspec_completion.py` passed 12 tests. |
| Repository and packaging structure | Passed with one warning | `make repo-hygiene`, `make verify-repo-consistency`, `packaging/scripts/openstock-secret-scan`, and `make validate-compose` exited `0`. `make verify-r2-ci` exited `0` with 18 OK, one warning and zero failures; the warning was from `systemd-analyze verify openstock-daily-pipeline.service`. |
| Static no-excuse audit | Pre-existing debt, no new finding | The checker found the existing 918-pure-LOC `chat/controller.py`, existing broad/silent exception boundaries and existing mutable `ChatError`. The issue #230 diff adds only typed catches immediately before the required generic unexpected-exception fallback; no unrelated controller refactor was attempted. |
| GitHub Actions on exact implementation commit | Pending | Exact implementation-commit CI will be recorded after the branch and PR exist. No merged-CI claim is inferred from local gates. |
