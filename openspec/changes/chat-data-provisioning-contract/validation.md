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
