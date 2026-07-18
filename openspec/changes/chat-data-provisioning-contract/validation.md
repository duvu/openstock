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
candidate's exact SHA will be recorded after the final local gate set is
committed.

Second candidate `3a77f328c8e414312a6a73f889777a74b1030ecc` is also
rejected. Exact-SHA review reproduced a missing legacy post-approval typed
mapping, truncation that could reactivate Rich markup, incomplete redaction for
common structured credential forms, and a broken private assistant error-type
contract for arbitrary tool implementation failures. Hands-on QA also found raw
credential-shaped detail in affected internal tool/session error summaries. Its runtime-audit pass and
local gate results are useful diagnostics but are not reusable as completion
evidence for the next commit.

The next correction also removes two validation-isolation leaks identified by
hands-on QA: the supplied-correlation fixture no longer exercises an ambient
localhost provider, and the swallowed slash-command exception test now owns a
temporary DuckDB warehouse instead of opening the default user warehouse.

Third candidate `b7ce47ff3831cd523014f966e930cb88cbed40d3` is rejected.
Exact-SHA review reproduced quoted multi-word and quoted/equal-sign
Authorization credential leaks, credentials whose marker fell inside the raw
head/tail crop, and credential-bearing `errors.jsonl` records incorrectly
marked redacted. Its passing lifecycle, path-parity and Rich-rendering results
are useful diagnostics but are not reusable as completion evidence.

Fourth candidate `5d769e17fff1eee411711f9558d37f3a0b38de65` is rejected.
Exact-SHA review proved that real approval of a safe current-symbol plan was
sent to the sandbox-only approval service before execution, leaving the turn
`PREPARED` with no tool trace. Review also reproduced standalone/quoted Basic
and legacy bearer credential leaks, plus raw context, likely-cause and
suggested-next fields in error records marked redacted. Passing results on that
SHA are diagnostic only and are not reusable for the next candidate.

Fifth candidate `07b2a676da1d7384057d870605d55b436b271067` is rejected.
Fresh exact-SHA review reproduced short and dotted standalone authorization
leaks, global false positives that rewrote ordinary `Basic analysis` prose and
host/port endpoints, incomplete nested sensitive-key handling, dropped error
records for JSON-valid non-string context keys, and content-bearing records
incorrectly labeled metadata-only. Its real approval/lifecycle QA and runtime
audit passes are diagnostic but not reusable for the next candidate.

Sixth candidate `9d7b6a7a89c1c949192e423b1dc7cf0d26ad4af7` is rejected.
Fresh exact-SHA review reproduced active Rich markup composed across otherwise
sanitized fields, a long Basic credential prefix surviving the bounded scan
crop, missed nested sensitive-key prefix forms, driver-qualified cropped-DSN
leaks, benign Bearer prose and IPv6/query/punctuated endpoint corruption, and
metadata-mode erasure of required closed-loop identifiers. Its core issue-path
and root runtime-audit passes are diagnostic only and are not reusable.

Seventh candidate `79146f656f3a009822f6da38a47244bc6fc05e4d` is rejected.
Fresh exact-SHA review reproduced a Basic credential whose decoded delimiter
fell beyond the scan window, standalone Bearer leaks plus financial-prose
corruption, malformed/cropped URI-userinfo leaks, camelCase nested-key leaks,
host-only DSN corruption, and `token_budgets` loss in the real memory-status
renderer. Four independent lanes rejected the snapshot; the QA lane and root
runtime audit passed its covered lifecycle paths, but none of that evidence is
reusable for the next candidate.

Eighth candidate `09ec4045b1e7a0359f55a7d773f09c93c1cb5496` is rejected.
Fresh exact-SHA review found that observability reintroduced broad substring
matching after the canonical key classifier, the renderer hid safe
`auth_status`, wrapped ordinary endpoints were corrupted, bounded scanning
could expose a JWT first-segment prefix or unsecured token, and secret-bearing
context key names survived in records labeled redacted. The context lane and
root runtime audit passed their covered paths; four other lanes rejected the
snapshot, so none of its evidence is reusable for the next candidate.

| Check | Outcome | Evidence |
|---|---|---|
| Initial red/green boundary regressions | Passed, then superseded | The first red run exposed five direct boundary failures and the first focused green run passed 26 tests. Exact-SHA review then demonstrated missing nested-executor, approval and legacy cases, so this evidence did not establish completion. |
| Exact-SHA review of `c440c71` | Failed | Goal, code-quality, QA, security and context review all rejected the snapshot. Runtime reproductions proved a credential-bearing DSN reached visible/persisted `tool_failed`, approval mapped three typed cases to generic `error`, and legacy execution persisted both trace-derived `tool_failed` and generic `error`. |
| Exact-SHA review of `3a77f32` | Failed | All five independent lanes rejected the snapshot. Reproductions proved legacy post-approval typed failures became generic, final slicing could reactivate escaped Rich markup, common structured credentials could survive public and audit-summary sanitization, and arbitrary tool failures no longer satisfied the established assistant error contract. |
| Corrective red/green surface regressions | Passed | The expanded test file produced eight expected failures before correction: missing structured public type, public ordinary/nested exceptions, three approval mappings, legacy duplication and active Rich markup. After correction, the three issue files passed 34 tests at `100%`, exit `0`; changed-file Ruff and format checks passed. |
| Second-review corrective red/green regressions | Passed, then superseded | Four legacy approval/Rich-boundary cases failed before correction; the assistant error-contract case and four credential-form cases then failed before their fixes; affected audit persistence retained a controlled private fixture before sanitization. The four issue files collected 23 passing cases before exact review found broader sanitizer gaps. |
| Exact-SHA review of `b7ce47f` | Failed | All five independent lanes rejected the snapshot. Reproductions proved quoted credentials and credential tails crossing the raw crop could survive public/audit sanitization; file-backed error records marked redacted also retained DSN, Basic, JWT and PEM fixtures. All immediate, approval, legacy, lifecycle and Rich-parser scenarios otherwise passed. |
| Third-review corrective red/green regressions | Passed locally, then superseded | New quoted/equal-sign Authorization and multi-word secret cases failed before correction; the public final-length assertions also exposed prefix-over-bound output. Review reproducers established the long crop and JSONL failures. After correction, the four issue files collected 41 passing cases, including complete actionable/validation length bounds and an automated `capture_exception` assertion over both stored message and stacktrace. A separate temporary-RunContext driver also wrote one redacted `errors.jsonl` record with zero controlled private fragments retained. |
| Third-correction full local gates | Passed, then superseded | The full vnalpha suite reached `100%`, exit `0`; R4 passed 81 tests; lint covered 697 files; installed-package verification passed 59/59; research answer/runtime evaluations passed 5/5 and 22/22; strict OpenSpec and 12 completion checks passed; repository hygiene, consistency, secret scan and compose validation passed; R2 CI passed with 18 OK, one existing systemd warning and zero failures. Exact review later rejected the candidate, so these results do not establish completion. |
| Exact-SHA review of `5d769e1` | Failed | Independent QA reproduced the real safe-plan approval dispatcher reaching the sandbox-only service and never executing the tool. Code, context and output-safety review reproduced standalone/quoted authorization, legacy bearer and auxiliary error-record field leaks. The goal lane's pass is superseded by these blocking runtime findings. |
| Fourth-review corrective red/green regressions | Passed locally, then superseded | The unmocked prepared-approval test failed before the dispatcher correction, and new Basic/quoted-authorization/complete-record assertions failed before the redaction correction. The expanded issue/chat/approval/observability selector passed 201 tests. Changed-file Ruff, format and LSP diagnostics passed, but exact review later rejected the candidate. |
| Fourth-correction full local gates | Passed, then superseded | The full vnalpha suite reached `100%`, exit `0`; R4 passed 81 tests; lint covered 697 files; the installed-package vertical passed 59/59 after overriding an unreachable inherited private package index with `PIP_INDEX_URL=https://pypi.org/simple`; research answer/runtime evaluations passed 5/5 and 22/22; strict OpenSpec and 12 completion checks passed; repository hygiene, consistency, secret scan and compose validation passed; R2 CI passed with 18 OK, one existing systemd warning and zero failures. Exact review later rejected the candidate, so these results do not establish completion. |
| Exact-SHA review of `07b2a67` | Failed | Goal, code, output-safety and context lanes rejected the snapshot; QA and the independent runtime audit passed the corrected real approval path. Reproductions proved valid short/dotted credentials leaked, benign global consumers were corrupted, nested context redaction could leak or drop the record, and metadata mode retained content. |
| Fifth-review corrective red/green regressions | Passed locally, then superseded | Nine focused cases failed before correction: short Basic/Bearer credentials, dotted Bearer grammar, two ordinary Basic-prose consumers, two host/port endpoints, non-string context keys and metadata content retention. After correction, the four issue suites plus chat-error, approval, observability, closed-loop-security, renderer, output-stream and TUI presentation coverage passed 235 tests. Exact review later rejected the candidate. |
| Fifth-correction full local gates | Passed, then superseded | The full vnalpha suite reached `100%`, exit `0`; R4 passed 81 tests; lint covered 697 files; the installed-package vertical passed 59/59 with `PIP_INDEX_URL=https://pypi.org/simple`; research answer/runtime evaluations passed 5/5 and 22/22; strict OpenSpec and 12 completion checks passed; repository hygiene, consistency, secret scan and compose validation passed; R2 CI passed with 18 OK, one existing systemd warning and zero failures. Exact review later rejected the candidate, so these results do not establish completion. |
| Exact-SHA review of `9d7b6a7` | Failed | All five independent lanes rejected the snapshot. Core immediate, real approved, legacy and unexpected lifecycle checks passed, but adversarial and compatibility reproducers established cross-field Rich activation, scan-cropped Basic exposure, incomplete nested-key and driver-DSN handling, benign Bearer/endpoint corruption and closed-loop metadata identity loss. The independent root runtime audit passed 56 issue cases and the real controller/app/tool lifecycle, but is diagnostic only. |
| Sixth-review corrective red/green regressions | Passed locally, then superseded | Seventeen focused cases failed before correction, covering field-composed Rich markup, a long Basic scan crop, standalone alphabetic Bearer credentials, nine benign Bearer/IPv6/query/punctuation/query-`@` consumers, three driver-qualified cropped DSNs, nested auth/credential/cookie key forms and closed-loop metadata identity. After correction, the five issue suites passed 73 tests and the explicit expanded approval/observability/CLI/TUI/closed-loop selector passed 252 tests. The forced metadata-mode closed-loop selection reduced from six candidate regressions to one independently confirmed pre-existing assertion mismatch already present on `07b2a67`; focused exception and structural-identity metadata regressions passed. Exact review later rejected the candidate. |
| Sixth-correction full local gates | Passed, then superseded | The full vnalpha suite reached `100%`, exit `0`; R4 passed 81 tests; lint covered 698 files; the installed-package vertical passed 59/59 with `PIP_INDEX_URL=https://pypi.org/simple`; research answer/runtime evaluations passed 5/5 and 22/22; strict OpenSpec and 12 completion checks passed; repository hygiene, consistency, secret scan and compose validation passed; R2 CI passed with 18 OK, one existing systemd warning and zero failures. Exact review later rejected the candidate. |
| Exact-SHA review of `79146f6` | Failed | Goal, code-quality, output-safety and context lanes rejected the snapshot; QA passed its exercised matrix, and the root lifecycle audit passed. The blocking reproducers covered scan-edge Basic, punctuated Bearer, financial prose, malformed/cropped URI userinfo, host-only DSNs, camelCase nested keys and real `token_budgets` rendering. |
| Seventh-review corrective red/green regressions | Passed locally, then superseded | Seventeen collected cases failed across two deliberate red runs, covering late-delimiter Basic scan crops, four punctuated Bearer credentials, three financial-prose forms, host-only DSNs, three malformed/single-letter-scheme URI forms, camelCase/operational-key compatibility, and query-colon/closing-punctuation endpoints. The corrected five issue suites passed 93 tests; the explicit 12-file issue/chat-error/approval/observability/closed-loop-security/renderer/output-stream/TUI selector passed 272 tests. A long HTTPS crop and bracketed host-only IPv6 were also added as reviewer-derived compatibility cases. Exact review later rejected the candidate. |
| Seventh-correction full local gates | Passed, then superseded | The full vnalpha suite reached `100%`, exit `0`; R4 passed 81 tests; lint covered 698 files; the installed-package vertical passed 59/59 with `PIP_INDEX_URL=https://pypi.org/simple`; research answer/runtime evaluations passed 5/5 and 22/22; strict OpenSpec and 12 completion checks passed; repository hygiene, consistency, secret scan and compose validation passed; R2 CI passed with 18 OK, one existing systemd warning and zero failures. Exact review later rejected the candidate. |
| Exact-SHA review of `09ec404` | Failed | Goal, code-quality, QA and output-safety lanes rejected the snapshot; context and the root runtime audit passed. Blocking reproducers covered observability token metrics, provider `auth_status`, wrapped endpoints, scan-edge/unsecured JWTs and secret-bearing persisted context key names. |
| Eighth-review corrective red/green regressions | Passed locally | Eight cases failed across two deliberate red runs before correction: scan-cropped and unsecured JWTs, three wrapped endpoints, persisted key-name/operational-metric handling, and two real `auth_status` assertions. The corrected six issue suites pass 100 tests; the explicit 13-file affected selector passes 279 tests. The new 102-line text-safety file keeps every issue regression file below 300 lines. |
| Manual controller/repository/tool lifecycle | Passed on rejected candidate | Exact-SHA runtime audit on `09ec404` passed immediate, approved, legacy and unexpected nested-tool scenarios plus 93 issue cases, but exact review rejected that snapshot and the evidence is diagnostic only. |
| Full vnalpha suite | Passed | `cd vnalpha && uv run --extra dev pytest -q` completed at `100%`, exit `0`, on the corrected worktree in one process. |
| R4 acceptance | Passed | `make verify-r4` completed 81 selected permission/session/trace/clear/persistence tests at `100%`, exit `0`. |
| Lint and formatting | Passed | `make lint-vnalpha` reported all checks passed and 699 files already formatted. Focused Ruff checks, format checks and LSP diagnostics also passed after the final test split. |
| Installed-package vertical | Passed | `PIP_INDEX_URL=https://pypi.org/simple make verify-vnalpha-package` passed 59/59, including the built Debian package's application-wheel fixture contract and runtime-replay evaluation. |
| Research evaluations | Passed | `make eval-research-answers` passed 5/5; `make eval-research-runtime` passed 22/22 with zero failures. |
| OpenSpec | Passed | `openspec validate chat-data-provisioning-contract --strict` reported valid; `python -m pytest -q scripts/tests/test_check_openspec_completion.py` passed 12 tests; apply instructions report 19/20 tasks with publication reconciliation intentionally pending. |
| Repository and packaging structure | Passed with one warning | `make repo-hygiene`, `make verify-repo-consistency`, `packaging/scripts/openstock-secret-scan`, and `make validate-compose` exited `0`. `make verify-r2-ci` exited `0` with 18 OK, one existing systemd verification warning and zero failures. |
| Static no-excuse audit | Pre-existing debt plus intentional fixtures | The inherited controller remains above the source-size threshold with existing broad/silent top-level boundaries and mutable `ChatError`. New issue regressions are split into 252-, 251-, 229-, 292-, 261- and 102-line files; their arbitrary `RuntimeError` fixtures are required to prove nested unexpected exceptions stay generic while preserving the private assistant error contract. The correction reuses two exact typed presentation helpers rather than refactoring unrelated controller responsibilities. |
| GitHub Actions on exact implementation commit | Pending | Exact implementation-commit CI will be recorded after the branch and PR exist. No merged-CI claim is inferred from local gates. |
