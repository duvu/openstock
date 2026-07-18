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

The prepared natural-language boundary presents only the explicitly public
`ActionableToolExecutionError` subtype as one sanitized, markup-neutralized and
bounded `[TOOL FAILED]` message plus one `tool_failed` transcript row. The
structured public payload contains readiness reason, bounded remediation and
correlation ID. Ordinary tool errors and arbitrary nested exceptions retain the
fixed generic retry text and `error` transcript type. The same typed presentation
is used for immediate, approved and legacy-compatible execution. Issue #228
stage/tool callbacks and canonical `tool_trace_event` persistence remain
unchanged.

Initial candidate `c440c71b2596f5cadcdacf7c4ae92d5790b49305` is rejected.
Five-lane review found that arbitrary tool runtime exceptions were wrapped into
the same public type, approval discarded actionable/validation presentation,
and the legacy trace callback created a semantic failure before the generic
fallback. No review or runtime-audit pass on that SHA is reusable. The corrected
candidate's exact SHA will be recorded in the PR evidence after this local gate
set is committed.

| Check | Outcome | Evidence |
|---|---|---|
| Initial red/green boundary regressions | Passed, then superseded | The first red run exposed five direct boundary failures and the first focused green run passed 26 tests. Exact-SHA review then demonstrated missing nested-executor, approval and legacy cases, so this evidence did not establish completion. |
| Exact-SHA review of `c440c71` | Failed | Goal, code-quality, QA, security and context review all rejected the snapshot. Runtime reproductions proved a credential-bearing DSN reached visible/persisted `tool_failed`, approval mapped three typed cases to generic `error`, and legacy execution persisted both trace-derived `tool_failed` and generic `error`. |
| Corrective red/green surface regressions | Passed | The expanded test file produced eight expected failures before correction: missing structured public type, public ordinary/nested exceptions, three approval mappings, legacy duplication and active Rich markup. After correction, the three issue files passed 34 tests at `100%`, exit `0`; changed-file Ruff and format checks passed. |
| Corrected affected chat/provisioning/lifecycle surface | Passed | The expanded issue #163/#228/chat/approval/executor selector completed at `100%`, exit `0`, including 15 test files and the real nested-executor regression. |
| Manual controller/repository/tool lifecycle | Pending exact-SHA rerun | The rejected candidate passed the immediate actionable P0 path. Immediate, approved, legacy and unexpected nested-tool scenarios will be rerun after the corrected commit exists so the evidence binds to its exact SHA. |
| Full vnalpha suite | Passed | `cd vnalpha && uv run --extra dev pytest -q` completed at `100%`, exit `0`, on the corrected worktree in one process. |
| R4 acceptance | Passed | `make verify-r4` completed 81 selected permission/session/trace/clear/persistence tests at `100%`, exit `0`. |
| Lint and formatting | Passed | `make lint-vnalpha` reported all checks passed and 695 files already formatted. Ruff LSP diagnostics reported no errors in all eight changed Python files. |
| Installed-package vertical | Passed | `PIP_INDEX_URL=https://pypi.org/simple make verify-vnalpha-package` passed 59/59, including the built Debian package's application-wheel fixture contract and runtime-replay evaluation. |
| Research evaluations | Passed | `make eval-research-answers` passed 5/5; `make eval-research-runtime` passed 22/22 with zero failures. |
| OpenSpec | Passed | `openspec validate chat-data-provisioning-contract --strict` reported valid; `python -m pytest -q scripts/tests/test_check_openspec_completion.py` passed 12 tests; apply instructions report 18/19 tasks with publication reconciliation intentionally pending. |
| Repository and packaging structure | Passed with one warning | `make repo-hygiene`, `make verify-repo-consistency`, `packaging/scripts/openstock-secret-scan`, and `make validate-compose` exited `0`. `make verify-r2-ci` exited `0` with 18 OK, one existing systemd verification warning and zero failures. |
| Static no-excuse audit | Pre-existing debt plus one intentional fixture | The checker reports the inherited 922-pure-LOC controller, existing broad/silent top-level boundaries and mutable `ChatError`. Its only correction-specific test finding is the deliberate arbitrary `RuntimeError` fixture required to prove nested unexpected exceptions stay generic. The correction adds no broad source conversion and reuses two exact typed presentation helpers rather than refactoring unrelated controller responsibilities. |
| GitHub Actions on exact implementation commit | Pending | Exact implementation-commit CI will be recorded after the branch and PR exist. No merged-CI claim is inferred from local gates. |
