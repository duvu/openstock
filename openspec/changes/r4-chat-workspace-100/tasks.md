# Tasks: R4 Chat Workspace 100% POC Completion

## 0. Completion governance

- [ ] 0.1 Treat this change as an implementation gate, not a docs-only completion claim.
- [ ] 0.2 Do not mark R4 as 100% until all tasks in this checklist are complete.
- [ ] 0.3 Keep `review.md` aligned with the actual implementation.
- [ ] 0.4 Add `make verify-r4` and use it as the R4 completion gate.
- [ ] 0.5 Update completion matrix and validation report only after validation evidence exists.

## 1. Chat session bootstrap

- [ ] 1.1 Add a helper to resume or create the latest active chat session for `surface` and `target_date`.
- [ ] 1.2 ChatPanel must run migrations before session lookup or creation.
- [ ] 1.3 ChatPanel must construct ChatController with a non-null `chat_session_id`.
- [ ] 1.4 ChatPanel must show a visible warning if session bootstrap fails.
- [ ] 1.5 Add tests proving ChatPanel controller has a non-null session id after mount.
- [ ] 1.6 Add tests proving target date is stored in the session row.

## 2. Controller-owned persistence

- [ ] 2.1 Add controller helpers for user, assistant, system/local-command, command-result, plan, and decision messages.
- [ ] 2.2 Persistence helpers must run migrations before writing when using a fresh connection.
- [ ] 2.3 Persistence helpers must close short-lived connections reliably.
- [ ] 2.4 Persistence failure must not crash the TUI, but must be observable in tests or warnings where practical.

## 3. Natural-language path

- [ ] 3.1 Persist the user prompt before planning.
- [ ] 3.2 Persist assistant answer in the auto safe-read path.
- [ ] 3.3 Persist assistant refusal.
- [ ] 3.4 Persist runtime error rows.
- [ ] 3.5 Persist plan-only preview with `plan_json`.
- [ ] 3.6 Persist approval-mode plan preview with `plan_json` before storing pending plan.
- [ ] 3.7 If permission review refuses a plan, persist refusal and do not store pending plan.
- [ ] 3.8 Add controller-level tests for all natural-language persistence paths.

## 4. Slash command path

- [ ] 4.1 Persist slash command input before command handling.
- [ ] 4.2 Persist successful command result.
- [ ] 4.3 Include `research_session_id` when available from command result metadata.
- [ ] 4.4 Persist validation errors.
- [ ] 4.5 Persist runtime failures.
- [ ] 4.6 Add controller-level tests for slash success and error paths.

## 5. Chat-local command path

- [ ] 5.1 Persist chat-local command input.
- [ ] 5.2 Persist chat-local command output.
- [ ] 5.3 Test `/help` persistence.
- [ ] 5.4 Test `/context` persistence.
- [ ] 5.5 Test `/plan` mode-change persistence.
- [ ] 5.6 Test unknown local command persistence.

## 6. Session lifecycle commands

- [ ] 6.1 `/new` must create a new chat session.
- [ ] 6.2 `/new` must switch ChatController to the new session id.
- [ ] 6.3 `/new` must clear pending plan state.
- [ ] 6.4 `/new` must preserve previous session transcript.
- [ ] 6.5 Document whether previous session remains active or is marked finished.
- [ ] 6.6 Add tests proving new messages after `/new` go to the new session.

## 7. Clear behavior

- [ ] 7.1 `/clear` command input must be persisted before hide behavior.
- [ ] 7.2 `/clear` default must hide visible rows through `is_visible=false` and `hidden_at`.
- [ ] 7.3 `/clear` default must preserve transcript rows.
- [ ] 7.4 Destructive clear must require the explicit `--forget` flag.
- [ ] 7.5 Help text must clearly distinguish `/clear` and `/clear --forget`.
- [ ] 7.6 Controller-level tests must prove both clear paths.

## 8. Plan lifecycle audit

- [ ] 8.1 Review plan permission before pending storage.
- [ ] 8.2 Review plan permission again before approval.
- [ ] 8.3 Persist plan preview with `plan_json`.
- [ ] 8.4 Pending plan state must include originating question and plan metadata.
- [ ] 8.5 Persist plan approval.
- [ ] 8.6 Persist approval result.
- [ ] 8.7 Persist plan cancellation only when a pending plan exists.
- [ ] 8.8 Approval with no pending plan must not create a fake approval audit row.
- [ ] 8.9 Add controller-level tests for preview, approval, cancellation, and refused plan cases.

## 9. Trace completion

- [ ] 9.1 ChatPanel-created controller must have an active session id so trace persistence is enabled.
- [ ] 9.2 Trace callback must persist RUNNING, SUCCESS, and FAILED events.
- [ ] 9.3 Trace event must include tool name and status.
- [ ] 9.4 Trace event must include duration when available.
- [ ] 9.5 Trace event must include trace id when available.
- [ ] 9.6 `/trace` must read persisted events for the active session.
- [ ] 9.7 `/trace` must show useful output when there are no events.
- [ ] 9.8 Add app-level test proving `/trace` works after ChatPanel session bootstrap.

## 10. Permission completion

- [ ] 10.1 Safe read-only plans may run in safe-read mode.
- [ ] 10.2 Approval-required plans must not run automatically in safe-read mode.
- [ ] 10.3 Approval-required plans may become pending only in approval mode.
- [ ] 10.4 Refused plans must not become pending.
- [ ] 10.5 Permanently restricted plans must never become pending or approvable.
- [ ] 10.6 Refusals must persist as assistant refusal rows.
- [ ] 10.7 Add controller-level tests for all permission states.

## 11. Controller-level persistence suite

- [ ] 11.1 Add `vnalpha/tests/test_r4_controller_persistence.py`.
- [ ] 11.2 Test natural-language user prompt persistence via controller method.
- [ ] 11.3 Test assistant answer persistence with mocked assistant call.
- [ ] 11.4 Test assistant refusal persistence with mocked assistant call.
- [ ] 11.5 Test slash command input/result persistence with mocked command executor.
- [ ] 11.6 Test chat-local input/output persistence via `/help`.
- [ ] 11.7 Test plan preview persistence with `plan_json`.
- [ ] 11.8 Test plan approval persistence.
- [ ] 11.9 Test plan cancellation persistence.
- [ ] 11.10 Test refused plan persistence.
- [ ] 11.11 Test trace event persistence with active session.
- [ ] 11.12 Tests must inspect `chat_message` rows, not just UI callbacks.

## 12. TUI integration proof

- [ ] 12.1 Update ChatPanel tests to assert active session id after mount.
- [ ] 12.2 Update TUI pilot tests to assert active session id in VnAlphaApp.
- [ ] 12.3 Test target date is stored in the session row.
- [ ] 12.4 Test input delegation preserves the same session id.
- [ ] 12.5 Test app-level approve/cancel uses the controller session.

## 13. R4 verification target

- [ ] 13.1 Add `verify-r4` to Makefile `.PHONY`.
- [ ] 13.2 `make verify-r4` must run all R4-specific tests.
- [ ] 13.3 `make verify-r4` must include `test_r4_controller_persistence.py`.
- [ ] 13.4 `make verify-r4` must fail non-zero on any R4 test failure.
- [ ] 13.5 Add `make verify-r4` output to validation report.

## 14. Documentation and evidence

- [ ] 14.1 Update completion matrix R4 row only after all R4 validation passes.
- [ ] 14.2 R4 completion matrix must list implementation, controller-level tests, TUI tests, negative tests, and runtime evidence.
- [ ] 14.3 R4 validation report must include exact `make verify-r4` result.
- [ ] 14.4 Remove or correct any claim that every turn persists if controller-level tests do not prove it.
- [ ] 14.5 Document R5+ deferred items separately from R4 completion.
- [ ] 14.6 Add manual R4 smoke steps for `/help`, `/context`, `/plan`, `/trace`, `/clear`, and `/new`.

## 15. Final R4 100% gate

- [ ] 15.1 `make lint-vnalpha` passes.
- [ ] 15.2 `make test-vnalpha` passes.
- [ ] 15.3 `make verify-r4` passes.
- [ ] 15.4 Controller-level persistence tests pass.
- [ ] 15.5 TUI session bootstrap tests pass.
- [ ] 15.6 Permission negative tests pass.
- [ ] 15.7 Trace tests pass.
- [ ] 15.8 Docs are corrected.
- [ ] 15.9 Validation report is updated.
- [ ] 15.10 No R4 blocker remains open.
- [ ] 15.11 Only then mark R4 as `100% POC-complete`.
