# Tasks: Close R0-R4 gaps to >90%

## 0. Completion governance

- [x] 0.1 Treat this change as a gap-closure change, not a replacement for the R0-R4 completion spec.
- [x] 0.2 Keep `openspec/changes/close-r0-r4-gaps-90/review.md` updated if implementation findings change.
- [x] 0.3 Add `vnalpha/docs/13-r0-r4-completion-matrix.md` with per-phase evidence.
- [x] 0.4 Add `vnalpha/docs/14-r0-r4-validation-report.md` with command outputs or `NOT RUN` justifications.
- [x] 0.5 Do not mark any R0-R4 phase above 90% until all blockers for that phase are closed.
- [x] 0.6 Do not mark tasks complete from OpenSpec status alone; require code/test/script/log evidence.

## 1. R0 — raise core pipeline confidence above 90%

### 1.1 CLI and Makefile verification

- [x] 1.1.1 Add `make verify-r0`.
- [x] 1.1.2 Ensure `make verify-r0` runs the offline E2E pipeline tests.
- [x] 1.1.3 Ensure `make verify-r0` runs feature metadata regression tests.
- [x] 1.1.4 Ensure `make verify-r0` runs migration upgrade tests.
- [x] 1.1.5 Ensure `make verify-r0` fails non-zero on any required R0 failure.
- [x] 1.1.6 Document `make verify-r0` in the operator/developer runbook.

### 1.2 Feature metadata tests

- [x] 1.2.1 Add test for `feature_data_status = MISSING_BENCHMARK` when VNINDEX data is absent.
- [x] 1.2.2 Add test for `feature_data_status = STALE_DATE` when target date has no exact symbol bar.
- [x] 1.2.3 Add test for `feature_data_status = EXACT_DATE` when target date has an exact symbol bar.
- [x] 1.2.4 Add test that `as_of_bar_date` records the actual bar date used.
- [x] 1.2.5 Add test that `benchmark_as_of_bar_date` records the actual benchmark bar date used.
- [x] 1.2.6 Add test that feature lineage includes provider, ingestion_run_id, source quality, actual bar date, and feature build version.

### 1.3 Migration upgrade tests

- [x] 1.3.1 Add test starting from an older minimal warehouse with only base R0 tables.
- [x] 1.3.2 Verify migrations add feature metadata columns without dropping existing rows.
- [x] 1.3.3 Verify migrations add assistant/chat/outcome tables without dropping existing rows.
- [x] 1.3.4 Verify migrations add candidate/outcome versioning columns without dropping existing rows.
- [x] 1.3.5 Verify migration can be run twice safely.

### 1.4 CLI boundary tests

- [x] 1.4.1 Add CLI test that explicit `--symbols` overrides `--universe`.
- [x] 1.4.2 Add CLI test that unknown `--universe` exits non-zero with useful error text.
- [x] 1.4.3 Add CLI test for `sync index --symbol VNINDEX` command shape using monkeypatched sync function.
- [x] 1.4.4 Add CLI test for `watchlist --date` no-data message.

## 2. R1 — raise architecture/docs confidence above 90%

- [x] 2.1 Update deployment architecture doc to match actual script and service paths.
- [x] 2.2 Add or update operator runbook with exact deploy, verify, backup, and rollback commands.
- [x] 2.3 Add R0-R4 completion matrix with current completion estimates and evidence links.
- [x] 2.4 Add validation report file with command results.
- [x] 2.5 Clearly mark R5+ deferred items.
- [x] 2.6 Document that ChatPanel delegates orchestration to ChatController after R4 fix.
- [x] 2.7 Document corrected daily pipeline command order.
- [x] 2.8 Document writer lock behavior and backup interaction.
- [x] 2.9 Document package build/install path and launchers.
- [x] 2.10 Document known limitations that remain after this change.

## 3. R2 — raise deploy and verify confidence above 90%

### 3.1 Correct pipeline execution

- [x] 3.1.1 Fix daily pipeline benchmark command to use `sync index --symbol VNINDEX`.
- [x] 3.1.2 Add `packaging/scripts/openstock-run-pipeline` or equivalent wrapper.
- [x] 3.1.3 Ensure wrapper acquires a lock that spans the whole pipeline.
- [x] 3.1.4 Ensure wrapper releases the lock on success and failure.
- [x] 3.1.5 Ensure wrapper supports `--dry-run`.
- [x] 3.1.6 Ensure wrapper supports date/start overrides.
- [x] 3.1.7 Ensure wrapper uses Docker Compose worker by default in deployed mode.
- [x] 3.1.8 Ensure wrapper can run a CI-safe fixture/static path or skip provider-backed work explicitly.
- [x] 3.1.9 Update `openstock-daily-pipeline.service` to call only the wrapper.
- [x] 3.1.10 Add tests or static assertions for the corrected command order.

### 3.2 Strengthen openstock-verify

- [x] 3.2.1 Make `openstock-verify --ci` run `docker compose config` when Docker is available.
- [x] 3.2.2 Make `openstock-verify --ci` statically verify localhost-only binding.
- [x] 3.2.3 Make `openstock-verify --ci` statically verify `vnalpha-worker` is profile-gated.
- [x] 3.2.4 Make `openstock-verify --ci` statically verify worker warehouse env/mount configuration.
- [x] 3.2.5 Make `openstock-verify --ci` run `bash -n` on deploy scripts.
- [x] 3.2.6 Make `openstock-verify --ci` verify systemd files when `systemd-analyze` is available.
- [x] 3.2.7 Make `openstock-verify --ci` verify package metadata/launcher files exist.
- [x] 3.2.8 Make `openstock-verify --ci` verify no TUI daemon is configured.
- [x] 3.2.9 Keep live service checks in default mode.
- [x] 3.2.10 Ensure required failures return non-zero.

### 3.3 Package proof

- [x] 3.3.1 Add or locate package build script and document its path.
- [x] 3.3.2 Add `make build-vnalpha-deb`.
- [x] 3.3.3 Add `make verify-vnalpha-deb`.
- [x] 3.3.4 Verify package artifact is produced.
- [x] 3.3.5 Verify launcher path for `vnalpha`.
- [x] 3.3.6 Verify launcher path for `vnalpha-poc`.
- [x] 3.3.7 Verify env template path for `/etc/vnalpha/vnalpha.env`.
- [x] 3.3.8 Verify package install does not delete warehouse data.
- [x] 3.3.9 Add package proof to validation report.

### 3.4 Backup and rollback proof

- [x] 3.4.1 Add static test for `openstock-backup-warehouse` lock behavior.
- [x] 3.4.2 Add static test for timestamped backup naming.
- [x] 3.4.3 Add manual validation step showing backup created.
- [x] 3.4.4 Add rollback section in operator runbook.
- [x] 3.4.5 Require `openstock-verify` after restore in docs.

### 3.5 Fresh-host validation

- [x] 3.5.1 Add fresh-host command checklist.
- [x] 3.5.2 Capture `docker compose config` output summary.
- [x] 3.5.3 Capture `docker compose up -d vnstock-service` result.
- [x] 3.5.4 Capture worker `init` result.
- [x] 3.5.5 Capture pipeline wrapper result.
- [x] 3.5.6 Capture `openstock-verify` result.
- [x] 3.5.7 Capture `openstock-backup-warehouse` result.
- [x] 3.5.8 Add final R2 completion estimate with evidence.

## 4. R3 — raise terminal workspace confidence above 90%

### 4.1 TUI pilot/integration tests

- [x] 4.1.1 Add Textual pilot test for app mount.
- [x] 4.1.2 Add pilot test for initial home screen.
- [x] 4.1.3 Add pilot test switching to watchlist screen.
- [x] 4.1.4 Add pilot test switching to commands screen.
- [x] 4.1.5 Add pilot test switching to assistant screen.
- [x] 4.1.6 Add pilot test switching to rejected screen.
- [x] 4.1.7 Add pilot test switching to quality screen.
- [x] 4.1.8 Add pilot test switching to outcomes screen.
- [x] 4.1.9 Add pilot test proving ChatPanel remains mounted after screen switching.
- [x] 4.1.10 Add pilot test for chat focus/toggle behavior.

### 4.2 TUI empty-state coverage

- [x] 4.2.1 Add empty warehouse test for watchlist screen.
- [x] 4.2.2 Add empty warehouse test for detail screen.
- [x] 4.2.3 Add empty warehouse test for quality screen.
- [x] 4.2.4 Add empty warehouse test for rejected screen.
- [x] 4.2.5 Add empty warehouse test for outcomes screen.
- [x] 4.2.6 Ensure no empty-state test crashes due to missing DuckDB file.

### 4.3 TUI workflow coverage

- [x] 4.3.1 Add test that watchlist row selection can open detail screen or call detail action.
- [x] 4.3.2 Add test that selected symbol/date context can be passed to chat/controller if supported.
- [x] 4.3.3 Replace placeholder TUI tests with meaningful assertions.
- [x] 4.3.4 Add `vnalpha tui --smoke` if full pilot tests are unstable.
- [x] 4.3.5 Document manual TUI smoke steps.

## 5. R4 — raise chat workspace confidence above 90%

### 5.1 Wire ChatPanel to ChatController

- [x] 5.1.1 ChatPanel creates or receives a ChatController instance.
- [x] 5.1.2 ChatPanel creates or resumes a chat_session for the target date.
- [x] 5.1.3 ChatPanel input submission calls `ChatController.handle_turn(raw)`.
- [x] 5.1.4 ChatPanel approval action calls `ChatController.approve_pending_plan()`.
- [x] 5.1.5 ChatPanel cancel action calls `ChatController.cancel_pending_plan()`.
- [x] 5.1.6 Stop using ChatPanel-local command registry dispatch.
- [x] 5.1.7 Stop using ChatPanel-local assistant dispatch.
- [x] 5.1.8 Update ChatPanel tests to assert delegation to ChatController.
- [x] 5.1.9 Update VnAlphaApp plan approval/cancel actions to call the controller reliably.

### 5.2 Persist every chat turn

- [x] 5.2.1 Persist normal user prompt as `chat_message`.
- [x] 5.2.2 Persist assistant answer as `chat_message`.
- [x] 5.2.3 Persist assistant refusal as `chat_message`.
- [x] 5.2.4 Persist slash command input as `chat_message`.
- [x] 5.2.5 Persist slash command result as `chat_message` linked to research_session where possible.
- [x] 5.2.6 Persist chat-local command input and output as `chat_message`.
- [x] 5.2.7 Persist plan preview with `plan_json`.
- [x] 5.2.8 Persist plan approval decision.
- [x] 5.2.9 Persist plan cancellation decision.
- [x] 5.2.10 Persist trace lifecycle events.
- [x] 5.2.11 Add tests for every persisted turn type.

### 5.3 Fix clear behavior

- [x] 5.3.1 Decide audit-preserving `/clear` behavior.
- [x] 5.3.2 If preserving transcript, add `is_visible` and `hidden_at` columns or equivalent.
- [x] 5.3.3 Make `/clear` hide visible messages but retain rows.
- [x] 5.3.4 Require explicit destructive flag for deletion, if deletion remains supported.
- [x] 5.3.5 Update help text to match actual behavior.
- [x] 5.3.6 Add tests proving `/clear` preserves audit history.
- [x] 5.3.7 Add tests proving destructive clear requires explicit flag.

### 5.4 Permission evaluation before pending plan

- [x] 5.4.1 Evaluate every planned tool before storing a pending plan.
- [x] 5.4.2 `ALLOW` tools may auto-run in safe-read mode.
- [x] 5.4.3 `ASK` tools may become pending only in approval mode.
- [x] 5.4.4 `DENY` tools produce a refusal in the current mode.
- [x] 5.4.5 `HARD_DENY` tools produce refusal and are never pending.
- [x] 5.4.6 Add tests proving restricted planned tools are not stored in `_pending_plan`.
- [x] 5.4.7 Add tests proving approval cannot run a restricted pending plan.
- [x] 5.4.8 Persist refusal messages for restricted planned tools.

### 5.5 Trace timeline

- [x] 5.5.1 ChatController trace callback persists trace events when chat_session exists.
- [x] 5.5.2 Trace events include tool name, status, duration, and tool_trace_id when available.
- [x] 5.5.3 `/trace` reads persisted trace events for current chat_session.
- [x] 5.5.4 Trace render shows useful output for no events.
- [x] 5.5.5 Add tests for trace persistence and `/trace` output.

### 5.6 Chat session lifecycle

- [x] 5.6.1 TUI start creates or resumes chat_session.
- [x] 5.6.2 `/new` creates a new chat_session and switches controller context.
- [x] 5.6.3 Chat session context stores target_date, selected symbol if available, execution mode, and pending-plan state where applicable.
- [x] 5.6.4 `/context` reads deterministic controller/session context.
- [x] 5.6.5 Add tests for session creation/resume/new/context.

## 6. Final validation gates

- [x] 6.1 `make install-vnalpha` passes.
- [x] 6.2 `make lint-vnalpha` passes or exceptions are documented.
- [x] 6.3 `make test-vnalpha` passes.
- [x] 6.4 `make verify-r0` passes.
- [x] 6.5 `make verify-r2-ci` passes.
- [x] 6.6 `docker compose config` passes.
- [x] 6.7 `openstock-verify --ci` passes.
- [x] 6.8 `openstock-run-pipeline --dry-run` passes.
- [x] 6.9 Package build/install verification passes or is explicitly deferred with justification.
- [x] 6.10 Manual deployed-host `openstock-verify` is recorded.
- [x] 6.11 Manual backup validation is recorded.
- [x] 6.12 TUI manual smoke is recorded.
- [x] 6.13 ChatPanel manual smoke is recorded.
- [x] 6.14 Completion matrix records R0-R4 all >= 90% with evidence.
- [x] 6.15 No task is marked complete without evidence.
