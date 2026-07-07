# Tasks: R4 Chat Workspace 100% POC Completion

## 0. Completion governance

- [x] 0.1 Treat this change as an implementation gate, not a docs-only completion claim.
- [x] 0.2 Do not mark R4 as 100% until all tasks in this checklist are complete.
- [x] 0.3 Keep `review.md` aligned with the actual implementation.
- [x] 0.4 Add `make verify-r4` and use it as the R4 completion gate.
- [x] 0.5 Update completion matrix and validation report only after validation evidence exists.

## 1. Chat session bootstrap

- [x] 1.1 Add a helper to resume or create the latest active chat session for `surface` and `target_date`.
- [x] 1.2 ChatPanel must run migrations before session lookup or creation.
- [x] 1.3 ChatPanel must construct ChatController with a non-null `chat_session_id`.
- [x] 1.4 ChatPanel must show a visible warning if session bootstrap fails.
- [x] 1.5 Add tests proving ChatPanel controller has a non-null session id after mount.
- [x] 1.6 Add tests proving target date is stored in the session row.

## 2. Controller-owned persistence

- [x] 2.1 Add controller helpers for user, assistant, system/local-command, command-result, plan, and decision messages.
- [x] 2.2 Persistence helpers must run migrations before writing when using a fresh connection.
- [x] 2.3 Persistence helpers must close short-lived connections reliably.
- [x] 2.4 Persistence failure must not crash the TUI, but must be observable in tests or warnings where practical.

## 3. Natural-language path

- [x] 3.1 Persist the user prompt before planning.
- [x] 3.2 Persist assistant answer in the auto safe-read path.
- [x] 3.3 Persist assistant refusal.
- [x] 3.4 Persist runtime error rows.
- [x] 3.5 Persist plan-only preview with `plan_json`.
- [x] 3.6 Persist approval-mode plan preview with `plan_json` before storing pending plan.
- [x] 3.7 If permission review refuses a plan, persist refusal and do not store pending plan.
- [x] 3.8 Add controller-level tests for all natural-language persistence paths.

## 4. Slash command path

- [x] 4.1 Persist slash command input before command handling.
- [x] 4.2 Persist successful command result.
- [x] 4.3 Include `research_session_id` when available from command result metadata.
- [x] 4.4 Persist validation errors.
- [x] 4.5 Persist runtime failures.
- [x] 4.6 Add controller-level tests for slash success and error paths.

## 5. Chat-local command path

- [x] 5.1 Persist chat-local command input.
- [x] 5.2 Persist chat-local command output.
- [x] 5.3 Test `/help` persistence.
- [x] 5.4 Test `/context` persistence.
- [x] 5.5 Test `/plan` mode-change persistence.
- [x] 5.6 Test unknown local command persistence.

## 6. Session lifecycle commands

- [x] 6.1 `/new` must create a new chat session.
- [x] 6.2 `/new` must switch ChatController to the new session id.
- [x] 6.3 `/new` must clear pending plan state.
- [x] 6.4 `/new` must preserve previous session transcript.
- [x] 6.5 Document whether previous session remains active or is marked finished.
- [x] 6.6 Add tests proving new messages after `/new` go to the new session.

## 7. Clear behavior

- [x] 7.1 `/clear` command input must be persisted before hide behavior.
- [x] 7.2 `/clear` default must hide visible rows through `is_visible=false` and `hidden_at`.
- [x] 7.3 `/clear` default must preserve transcript rows.
- [x] 7.4 Destructive clear must require the explicit `--forget` flag.
- [x] 7.5 Help text must clearly distinguish `/clear` and `/clear --forget`.
- [x] 7.6 Controller-level tests must prove both clear paths.

## 8. Plan lifecycle audit

- [x] 8.1 Review plan permission before pending storage.
- [x] 8.2 Review plan permission again before approval.
- [x] 8.3 Persist plan preview with `plan_json`.
- [x] 8.4 Pending plan state must include originating question and plan metadata.
- [x] 8.5 Persist plan approval.
- [x] 8.6 Persist approval result.
- [x] 8.7 Persist plan cancellation only when a pending plan exists.
- [x] 8.8 Approval with no pending plan must not create a fake approval audit row.
- [x] 8.9 Add controller-level tests for preview, approval, cancellation, and refused plan cases.

## 9. Trace completion

- [x] 9.1 ChatPanel-created controller must have an active session id so trace persistence is enabled.
- [x] 9.2 Trace callback must persist RUNNING, SUCCESS, and FAILED events.
- [x] 9.3 Trace event must include tool name and status.
- [x] 9.4 Trace event must include duration when available.
- [x] 9.5 Trace event must include trace id when available.
- [x] 9.6 `/trace` must read persisted events for the active session.
- [x] 9.7 `/trace` must show useful output when there are no events.
- [x] 9.8 Add app-level test proving `/trace` works after ChatPanel session bootstrap.

## 10. Permission completion

- [x] 10.1 Safe read-only plans may run in safe-read mode.
- [x] 10.2 Approval-required plans must not run automatically in safe-read mode.
- [x] 10.3 Approval-required plans may become pending only in approval mode.
- [x] 10.4 Refused plans must not become pending.
- [x] 10.5 Permanently restricted plans must never become pending or approvable.
- [x] 10.6 Refusals must persist as assistant refusal rows.
- [x] 10.7 Add controller-level tests for all permission states.

## 11. Controller-level persistence suite

- [x] 11.1 Add `vnalpha/tests/test_r4_controller_persistence.py`.
- [x] 11.2 Test natural-language user prompt persistence via controller method.
- [x] 11.3 Test assistant answer persistence with mocked assistant call.
- [x] 11.4 Test assistant refusal persistence with mocked assistant call.
- [x] 11.5 Test slash command input/result persistence with mocked command executor.
- [x] 11.6 Test chat-local input/output persistence via `/help`.
- [x] 11.7 Test plan preview persistence with `plan_json`.
- [x] 11.8 Test plan approval persistence.
- [x] 11.9 Test plan cancellation persistence.
- [x] 11.10 Test refused plan persistence.
- [x] 11.11 Test trace event persistence with active session.
- [x] 11.12 Tests must inspect `chat_message` rows, not just UI callbacks.

## 12. TUI integration proof

- [x] 12.1 Update ChatPanel tests to assert active session id after mount.
- [x] 12.2 Update TUI pilot tests to assert active session id in VnAlphaApp.
- [x] 12.3 Test target date is stored in the session row.
- [x] 12.4 Test input delegation preserves the same session id.
- [x] 12.5 Test app-level approve/cancel uses the controller session.

## 13. R4 verification target

- [x] 13.1 Add `verify-r4` to Makefile `.PHONY`.
- [x] 13.2 `make verify-r4` must run all R4-specific tests.
- [x] 13.3 `make verify-r4` must include `test_r4_controller_persistence.py`.
- [x] 13.4 `make verify-r4` must fail non-zero on any R4 test failure.
- [x] 13.5 Add `make verify-r4` output to validation report.

## 14. Documentation and evidence

- [x] 14.1 Update completion matrix R4 row only after all R4 validation passes.
- [x] 14.2 R4 completion matrix must list implementation, controller-level tests, TUI tests, negative tests, and runtime evidence.
- [x] 14.3 R4 validation report must include exact `make verify-r4` result.
- [x] 14.4 Remove or correct any claim that every turn persists if controller-level tests do not prove it.
- [x] 14.5 Document R5+ deferred items separately from R4 completion.
- [x] 14.6 Add manual R4 smoke steps for `/help`, `/context`, `/plan`, `/trace`, `/clear`, and `/new`.

## 15. Final R4 100% gate

- [x] 15.1 `make lint-vnalpha` passes.
- [x] 15.2 `make test-vnalpha` passes.
- [x] 15.3 `make verify-r4` passes.
- [x] 15.4 Controller-level persistence tests pass.
- [x] 15.5 TUI session bootstrap tests pass.
- [x] 15.6 Permission negative tests pass.
- [x] 15.7 Trace tests pass.
- [x] 15.8 Docs are corrected.
- [x] 15.9 Validation report is updated.
- [x] 15.10 No R4 blocker remains open.
- [x] 15.11 Only then mark R4 as `100% POC-complete`.
