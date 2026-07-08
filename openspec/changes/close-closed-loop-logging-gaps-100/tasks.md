# Tasks: Close closed-loop logging and AI repair gaps to 100%

## 0. Governance

- [ ] 0.1 Keep this change implementation-focused; do not mark complete for docs-only work.
- [ ] 0.2 Do not mark a task complete without code, tests, scripts, and validation evidence where applicable.
- [ ] 0.3 Preserve safety boundary: no broker/order/account/portfolio/margin/trading execution features.
- [ ] 0.4 Preserve redaction-by-default behavior.
- [ ] 0.5 Preserve best-effort logging: logging failures must not crash normal workflow.
- [ ] 0.6 Separate observed facts from inferred likely causes in summaries and repair prompts.
- [ ] 0.7 Add `validation.md` before marking this change ready for archive.

## 1. Correlation ID unification

- [ ] 1.1 Identify all correlation APIs currently used by structlog and file observability.
- [ ] 1.2 Choose one shared correlation source of truth.
- [ ] 1.3 Make `vnalpha.core.logging.set_correlation_id()` and observability writers use the same value.
- [ ] 1.4 Ensure CLI command events do not write `correlation_id="unset"` after a command starts.
- [ ] 1.5 Ensure ChatController natural-language turns use one correlation ID across audit/error/trace events.
- [ ] 1.6 Ensure tool events inherit the active command/chat correlation ID.
- [ ] 1.7 Ensure pipeline, repair, deploy, and rollback flows generate and propagate non-empty correlation IDs.
- [ ] 1.8 Add test proving command/audit/error/trace events share one correlation ID.
- [ ] 1.9 Add regression test preventing `unset` correlation IDs in normal instrumented command paths.

## 2. Audit writer compatibility

- [ ] 2.1 Extend `log_audit()` to accept optional `module` and `function` parameters.
- [ ] 2.2 Extend `log_audit()` to accept optional `session_id`, `object_type`, and `object_id` parameters if useful.
- [ ] 2.3 Ensure unsupported optional metadata does not raise `TypeError`.
- [ ] 2.4 Update call sites to pass module/function consistently.
- [ ] 2.5 Add test proving `log_audit(..., module="...")` writes an event.
- [ ] 2.6 Add test proving `TOOL_REFUSED` is actually written to `audit.jsonl`.
- [ ] 2.7 Add test proving `ASSISTANT_ANSWER_LOGGED` is written when AssistantApp succeeds.
- [ ] 2.8 Add test proving `CHAT_REFUSAL` is written on refusal paths.

## 3. CLI command lifecycle logging

- [ ] 3.1 Add command lifecycle helper/decorator/context manager.
- [ ] 3.2 Ensure every command starts or reuses a run context.
- [ ] 3.3 Ensure every command generates a correlation ID.
- [ ] 3.4 Emit `COMMAND_STARTED` before command body.
- [ ] 3.5 Emit `COMMAND_SUCCEEDED` after successful completion.
- [ ] 3.6 Emit `COMMAND_FAILED` for Typer exits and handled failures.
- [ ] 3.7 Capture exception details in `errors.jsonl` for unhandled exceptions.
- [ ] 3.8 Capture `duration_ms`.
- [ ] 3.9 Capture `exit_code` when available.
- [ ] 3.10 Capture bounded stdout/stderr tails where feasible.
- [ ] 3.11 Instrument `init`.
- [ ] 3.12 Instrument `sync symbols`.
- [ ] 3.13 Instrument `sync ohlcv`.
- [ ] 3.14 Instrument `sync index`.
- [ ] 3.15 Instrument `build canonical`.
- [ ] 3.16 Instrument `build features`.
- [ ] 3.17 Instrument `score`.
- [ ] 3.18 Instrument `watchlist`.
- [ ] 3.19 Instrument `cmd`.
- [ ] 3.20 Instrument `ask`.
- [ ] 3.21 Instrument `outcome evaluate`.
- [ ] 3.22 Instrument `logs bundle/summarize/doctor`.
- [ ] 3.23 Add CLI success-path tests.
- [ ] 3.24 Add CLI failure-path tests.

## 4. Error and warning coverage hardening

- [ ] 4.1 Ensure swallowed exceptions in ChatController are captured before swallowing.
- [ ] 4.2 Ensure ChatController slash command errors write `errors.jsonl`.
- [ ] 4.3 Ensure AssistantApp AssistantError paths call `capture_exception()`.
- [ ] 4.4 Ensure unexpected AssistantApp errors call `capture_exception()`.
- [ ] 4.5 Ensure domain logging captures failures, not only start/success.
- [ ] 4.6 Ensure warnings for data quality degradation use `capture_warning()` or equivalent.
- [ ] 4.7 Add tests for captured swallowed exceptions.
- [ ] 4.8 Add tests for AssistantApp failure logging.

## 5. Tool and trace lifecycle hardening

- [ ] 5.1 Ensure tool started/succeeded/failed events include parent span where available.
- [ ] 5.2 Ensure permission-denied tools emit both trace and audit events.
- [ ] 5.3 Ensure failed tools emit `errors.jsonl` entries or equivalent error events.
- [ ] 5.4 Ensure tool input/output respects content mode.
- [ ] 5.5 Add tests for successful tool trace with correlation ID.
- [ ] 5.6 Add tests for failed tool trace with correlation ID.
- [ ] 5.7 Add tests for refused tool audit and trace.

## 6. Pipeline script structured logging

- [ ] 6.1 Add safe JSONL logging helper for shell scripts.
- [ ] 6.2 Ensure JSON strings are escaped safely; do not rely on raw `echo` for arbitrary command text.
- [ ] 6.3 In `openstock-run-pipeline`, log `PIPELINE_STARTED`.
- [ ] 6.4 Log each step `PIPELINE_STEP_STARTED`.
- [ ] 6.5 Log each step `PIPELINE_STEP_SUCCEEDED`.
- [ ] 6.6 Log each step `PIPELINE_STEP_FAILED`.
- [ ] 6.7 Log `PIPELINE_COMPLETED`.
- [ ] 6.8 Log `PIPELINE_FAILED` before exit on failure.
- [ ] 6.9 Include command text, duration, exit code, stdout/stderr tail where feasible.
- [ ] 6.10 Add dry-run or fixture test proving step events are written.
- [ ] 6.11 Add bash/static test proving script JSONL is valid.

## 7. Verify script structured logging

- [ ] 7.1 Instrument `openstock-verify` check helper functions.
- [ ] 7.2 Log `VERIFY_STARTED`.
- [ ] 7.3 Log `VERIFY_CHECK_PASSED` for each ok check.
- [ ] 7.4 Log `VERIFY_CHECK_WARNED` for each warn check.
- [ ] 7.5 Log `VERIFY_CHECK_SKIPPED` for each skip check.
- [ ] 7.6 Log `VERIFY_CHECK_FAILED` for each fail check.
- [ ] 7.7 Log `VERIFY_RUN_COMPLETED` with pass/warn/fail counts.
- [ ] 7.8 Include check name, status, duration, and details.
- [ ] 7.9 Add `openstock-verify --ci` fixture test for JSONL events.
- [ ] 7.10 Add parseability test for verify JSONL output.

## 8. Backup and restore logging

- [ ] 8.1 Log `BACKUP_STARTED`.
- [ ] 8.2 Log lock-file failure as `BACKUP_FAILED`.
- [ ] 8.3 Log missing warehouse as `BACKUP_FAILED`.
- [ ] 8.4 Log copy failure as `BACKUP_FAILED`.
- [ ] 8.5 Log `BACKUP_CREATED` on success.
- [ ] 8.6 Add backup script fixture tests for success and failure paths.
- [ ] 8.7 If restore script exists or is added, log `RESTORE_STARTED`, `RESTORE_COMPLETED`, and `RESTORE_FAILED`.

## 9. Repair bundle generation

- [ ] 9.1 Add `vnalpha repair prepare --latest` or equivalent.
- [ ] 9.2 Resolve latest run directory from log root.
- [ ] 9.3 Create `logs/bundles/<bundle-id>/`.
- [ ] 9.4 Copy selected raw logs into `raw-logs/`.
- [ ] 9.5 Generate `ai-agent-summary.md` if missing or stale.
- [ ] 9.6 Generate `ai-coding-prompt.md`.
- [ ] 9.7 Generate `reproduction.md`.
- [ ] 9.8 Generate rich `manifest.json`.
- [ ] 9.9 Include source run ID(s), source branch, source commit SHA, redaction mode, generated timestamp.
- [ ] 9.10 Include top errors and warnings.
- [ ] 9.11 Include failed commands with exit code and output tails.
- [ ] 9.12 Include likely modules/files inferred from errors/traces.
- [ ] 9.13 Include required validation commands.
- [ ] 9.14 Include safety guardrails.
- [ ] 9.15 Ensure default bundle excludes secrets and unsafe files.
- [ ] 9.16 Log `REPAIR_PREPARED`.
- [ ] 9.17 Add tests for repair bundle generation.
- [ ] 9.18 Add tests for repair bundle redaction and exclusions.

## 10. AI coding prompt quality

- [ ] 10.1 Prompt includes objective.
- [ ] 10.2 Prompt includes source commit/branch.
- [ ] 10.3 Prompt includes observed failures.
- [ ] 10.4 Prompt includes reproduction steps.
- [ ] 10.5 Prompt includes relevant log excerpts.
- [ ] 10.6 Prompt includes likely modules/files to inspect.
- [ ] 10.7 Prompt includes explicit constraints and guardrails.
- [ ] 10.8 Prompt includes required validation commands.
- [ ] 10.9 Prompt includes expected output format.
- [ ] 10.10 Prompt distinguishes facts from likely causes.
- [ ] 10.11 Add tests for prompt sections.

## 11. Repair status and validation

- [ ] 11.1 Add `vnalpha repair status <repair-id>`.
- [ ] 11.2 Add `vnalpha repair validate <repair-id>`.
- [ ] 11.3 Store repair status as local JSON.
- [ ] 11.4 Record source run IDs and bundle ID.
- [ ] 11.5 Record proposed fix branch when provided.
- [ ] 11.6 Record PR number/URL when provided.
- [ ] 11.7 Record commit SHA(s) when provided.
- [ ] 11.8 Run or dry-run validation command list.
- [ ] 11.9 Log `REPAIR_VALIDATION_STARTED`.
- [ ] 11.10 Log `REPAIR_VALIDATION_PASSED` or `REPAIR_VALIDATION_FAILED`.
- [ ] 11.11 Store command result details: status, exit code, duration, output tails.
- [ ] 11.12 Add tests for repair status display.
- [ ] 11.13 Add tests for validation pass and fail paths.

## 12. Deploy verify/promote/rollback gate

- [ ] 12.1 Add `vnalpha deploy verify` or equivalent.
- [ ] 12.2 Add `vnalpha deploy promote <candidate>` or equivalent.
- [ ] 12.3 Add `vnalpha deploy rollback <deployment-id>` or equivalent.
- [ ] 12.4 Record previous deployed version.
- [ ] 12.5 Record candidate version.
- [ ] 12.6 Log `DEPLOY_VERIFY_STARTED`.
- [ ] 12.7 Log `DEPLOY_VERIFY_PASSED` or `DEPLOY_VERIFY_FAILED`.
- [ ] 12.8 Block promotion when validation is missing.
- [ ] 12.9 Block promotion when validation failed.
- [ ] 12.10 Log `DEPLOY_BLOCKED` with reason.
- [ ] 12.11 Log `DEPLOY_PROMOTED` when promotion succeeds.
- [ ] 12.12 Log post-deploy smoke result.
- [ ] 12.13 Log rollback availability.
- [ ] 12.14 Log rollback start/result.
- [ ] 12.15 Add tests for blocked promotion.
- [ ] 12.16 Add tests for dry-run promotion event logging.
- [ ] 12.17 Add tests for rollback event logging.

## 13. Closed-loop end-to-end fixture

- [ ] 13.1 Add fixture command or test helper that intentionally fails safely.
- [ ] 13.2 Verify failure writes command/audit/error events.
- [ ] 13.3 Generate summary from failed run.
- [ ] 13.4 Run repair prepare on failed run.
- [ ] 13.5 Verify repair bundle contains prompt/reproduction/manifest/raw logs.
- [ ] 13.6 Run repair validate with failing validation command.
- [ ] 13.7 Verify validation failure is recorded.
- [ ] 13.8 Attempt deploy promote and verify it is blocked.
- [ ] 13.9 Verify `DEPLOY_BLOCKED` is logged.
- [ ] 13.10 Add optional dry-run pass scenario that records deploy success without real production deployment.

## 14. Documentation

- [ ] 14.1 Update observability docs with correlation model.
- [ ] 14.2 Document `vnalpha repair prepare/status/validate`.
- [ ] 14.3 Document repair bundle layout.
- [ ] 14.4 Document AI coding prompt contract.
- [ ] 14.5 Document deploy verify/promote/rollback gates.
- [ ] 14.6 Document manual vs AI-assisted vs automatic steps.
- [ ] 14.7 Document rollback assumptions.
- [ ] 14.8 Document how to hand logs/bundles to KiloCode/Codex/Sisyphus.

## 15. Validation evidence

- [ ] 15.1 Run `make test-vnalpha`.
- [ ] 15.2 Run `make lint-vnalpha`.
- [ ] 15.3 Run `make verify-r0`.
- [ ] 15.4 Run `make verify-r2-ci`.
- [ ] 15.5 Run `make verify-r4`.
- [ ] 15.6 Run `openstock-verify --ci`.
- [ ] 15.7 Run pipeline dry-run / fixture and inspect JSONL.
- [ ] 15.8 Run repair prepare fixture and inspect bundle.
- [ ] 15.9 Run repair validate fixture and inspect repair status.
- [ ] 15.10 Run deploy promote blocked fixture and inspect deploy events.
- [ ] 15.11 Add `validation.md` with command outputs or summarized evidence.
