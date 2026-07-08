# Tasks: File-based observability for AI-agent-readable logs

## 0. Completion governance

- [ ] 0.1 Treat this change as an implementation requirement for file-based observability, not a docs-only completion claim.
- [ ] 0.2 Do not mark tasks complete until code, tests, scripts, or validation logs exist.
- [ ] 0.3 Keep `review.md` updated if implementation findings change.
- [ ] 0.4 Add validation evidence when implementation PRs run tests or scripts.
- [ ] 0.5 Document any intentionally deferred tasks with reason and owner.

## 1. Log directory and run model

- [ ] 1.1 Add configurable log root resolution.
- [ ] 1.2 Use `/var/log/openstock` for packaged/deployed mode when writable.
- [ ] 1.3 Use `~/.local/state/openstock/logs` as local fallback.
- [ ] 1.4 Add run directory creation under `runs/<run-id>/`.
- [ ] 1.5 Add `latest` symlink or `latest.txt` pointer fallback.
- [ ] 1.6 Write `environment.json` with branch/commit/python/platform/config summary where available.
- [ ] 1.7 Write per-run `README.md` explaining file meanings.
- [ ] 1.8 Add tests for run directory creation and latest pointer behavior.

## 2. JSONL sink and schemas

- [ ] 2.1 Add JSONL append helper that writes one valid JSON object per line.
- [ ] 2.2 Ensure writer creates parent directories.
- [ ] 2.3 Ensure writer is best-effort and does not crash core workflows.
- [ ] 2.4 Add schema definitions for audit events.
- [ ] 2.5 Add schema definitions for app log events.
- [ ] 2.6 Add schema definitions for error events.
- [ ] 2.7 Add schema definitions for trace events.
- [ ] 2.8 Add schema definitions for command events.
- [ ] 2.9 Commit schema JSON files or generated schema docs.
- [ ] 2.10 Add tests proving JSONL lines parse as valid JSON.
- [ ] 2.11 Add tests proving required fields are present.

## 3. Redaction and content policy

- [ ] 3.1 Add redaction module for sensitive runtime values.
- [ ] 3.2 Redact sensitive keys in dictionaries before writing logs.
- [ ] 3.3 Redact sensitive-looking values in strings before writing logs.
- [ ] 3.4 Add configurable content mode: `metadata`, `redacted`, `full`.
- [ ] 3.5 Default content mode to `redacted` or safer.
- [ ] 3.6 Ensure `full` mode requires explicit opt-in.
- [ ] 3.7 Add tests for dictionary redaction.
- [ ] 3.8 Add tests for string redaction.
- [ ] 3.9 Add tests proving default mode does not write unredacted sensitive values.

## 4. Correlation and context propagation

- [ ] 4.1 Add run context object containing `run_id`, surface, actor, and log paths.
- [ ] 4.2 Add correlation context object containing `correlation_id` and optional parent span.
- [ ] 4.3 Generate a new correlation ID for each CLI command execution.
- [ ] 4.4 Generate a new correlation ID for each ChatController turn.
- [ ] 4.5 Generate a new correlation ID for each pipeline run.
- [ ] 4.6 Generate child span IDs for pipeline steps and tool calls.
- [ ] 4.7 Propagate correlation ID to audit, command, trace, app, and error events.
- [ ] 4.8 Add tests proving related events share a correlation ID.

## 5. CLI and command logging

- [ ] 5.1 Instrument the main CLI entrypoint.
- [ ] 5.2 Write command start event to `commands.jsonl`.
- [ ] 5.3 Write command success event to `commands.jsonl`.
- [ ] 5.4 Write command failure event to `commands.jsonl`.
- [ ] 5.5 Capture `duration_ms`.
- [ ] 5.6 Capture `exit_code` when available.
- [ ] 5.7 Capture bounded stdout/stderr tails when available.
- [ ] 5.8 Write high-level command audit event to `audit.jsonl`.
- [ ] 5.9 Instrument `CommandExecutor` so TUI/chat commands are also logged.
- [ ] 5.10 Add tests for CLI command success and failure log events.

## 6. Error and warning logging

- [ ] 6.1 Add centralized exception capture helper.
- [ ] 6.2 Write exceptions to `errors.jsonl`.
- [ ] 6.3 Include error type, message, module, function, stack trace, and stack trace hash.
- [ ] 6.4 Include likely cause only when deterministic or explicitly inferred.
- [ ] 6.5 Include suggested next step when useful.
- [ ] 6.6 Instrument currently best-effort `except Exception` paths to log before swallowing.
- [ ] 6.7 Log warnings for degraded behavior and skipped validations.
- [ ] 6.8 Add tests for error capture.
- [ ] 6.9 Add tests proving logging failure does not crash the original workflow.

## 7. ChatController and assistant logging

- [ ] 7.1 Log `CHAT_TURN_STARTED` for each ChatController natural-language turn.
- [ ] 7.2 Log user prompt metadata according to content mode.
- [ ] 7.3 Log `PLAN_PREVIEWED` when a plan is generated.
- [ ] 7.4 Log `PLAN_APPROVED` when a plan is approved.
- [ ] 7.5 Log `PLAN_CANCELLED` when a plan is cancelled.
- [ ] 7.6 Log assistant answer metadata according to content mode.
- [ ] 7.7 Log assistant refusal as audit and error/warning when appropriate.
- [ ] 7.8 Log ChatController runtime errors to `errors.jsonl`.
- [ ] 7.9 Instrument `AssistantApp.ask` with trace events.
- [ ] 7.10 Add tests for chat turn logging.
- [ ] 7.11 Add tests for plan lifecycle logging.
- [ ] 7.12 Add tests for refusal logging.

## 8. Tool and trace logging

- [ ] 8.1 Instrument LocalToolRegistry or equivalent tool execution path.
- [ ] 8.2 Write `TOOL_CALL_STARTED` trace events.
- [ ] 8.3 Write `TOOL_CALL_SUCCEEDED` trace events.
- [ ] 8.4 Write `TOOL_CALL_FAILED` trace events.
- [ ] 8.5 Write `TOOL_REFUSED` audit events for denied tools.
- [ ] 8.6 Include tool name, status, duration, correlation ID, and parent span.
- [ ] 8.7 Do not log full tool output unless content mode allows it.
- [ ] 8.8 Add tests for successful tool trace.
- [ ] 8.9 Add tests for failed tool trace.
- [ ] 8.10 Add tests for refused tool audit.

## 9. Pipeline, verify, and backup script logging

- [ ] 9.1 Instrument `openstock-run-pipeline` with run start/completion events.
- [ ] 9.2 Log each pipeline step start/success/failure.
- [ ] 9.3 Include command text, duration, status, and output tail for each step.
- [ ] 9.4 Instrument `openstock-verify` with verify check events.
- [ ] 9.5 Instrument `openstock-backup-warehouse` with backup events.
- [ ] 9.6 Add restore logging if restore script exists or is added later.
- [ ] 9.7 Ensure shell-script logging writes valid JSONL.
- [ ] 9.8 Add shell/static tests for JSONL syntax or helper invocation.

## 10. Data pipeline domain logging

- [ ] 10.1 Log warehouse migration start/success/failure.
- [ ] 10.2 Log data sync start/success/failure.
- [ ] 10.3 Log feature build start/success/failure and row counts.
- [ ] 10.4 Log scoring start/success/failure and candidate counts.
- [ ] 10.5 Log watchlist generation start/success/failure and selected counts.
- [ ] 10.6 Log outcome evaluation start/success/failure and evaluation counts.
- [ ] 10.7 Log data quality warnings.
- [ ] 10.8 Add tests for at least one success and one failure path per major domain group.

## 11. AI-agent summary

- [ ] 11.1 Add summary generator for `ai-agent-summary.md`.
- [ ] 11.2 Summarize run metadata.
- [ ] 11.3 Summarize what happened.
- [ ] 11.4 Summarize errors and warnings.
- [ ] 11.5 Summarize failed commands.
- [ ] 11.6 Summarize suspicious patterns.
- [ ] 11.7 List likely involved files or modules.
- [ ] 11.8 List suggested investigation steps.
- [ ] 11.9 Link raw JSONL files.
- [ ] 11.10 Distinguish observed facts from likely causes.
- [ ] 11.11 Add tests for summary generation.

## 12. Log commands and bundle

- [ ] 12.1 Add `vnalpha logs latest` or equivalent.
- [ ] 12.2 Add `vnalpha logs show --latest` or equivalent.
- [ ] 12.3 Add `vnalpha logs errors --latest` or equivalent.
- [ ] 12.4 Add `vnalpha logs summarize --latest` or equivalent.
- [ ] 12.5 Add `vnalpha logs doctor --latest` or equivalent.
- [ ] 12.6 Add `vnalpha logs bundle --latest` or equivalent.
- [ ] 12.7 Ensure bundle excludes unsafe files by default.
- [ ] 12.8 Ensure bundle contains summary, JSONL logs, schemas, and environment summary.
- [ ] 12.9 Add tests for logs command group.
- [ ] 12.10 Add tests for bundle output.

## 13. Documentation and validation

- [ ] 13.1 Add developer docs explaining log layout.
- [ ] 13.2 Add operator docs explaining how to collect logs for an AI agent.
- [ ] 13.3 Document content logging modes and redaction behavior.
- [ ] 13.4 Document retention/cleanup assumptions.
- [ ] 13.5 Add validation report with command outputs.
- [ ] 13.6 Add examples of `ai-agent-summary.md`.
- [ ] 13.7 Add examples of JSONL event lines.

## 14. Acceptance gates

- [ ] 14.1 `make test-vnalpha` passes.
- [ ] 14.2 `make lint-vnalpha` passes or exceptions are documented.
- [ ] 14.3 Redaction tests pass.
- [ ] 14.4 JSONL schema/parse tests pass.
- [ ] 14.5 Correlation propagation tests pass.
- [ ] 14.6 CLI command logging tests pass.
- [ ] 14.7 Chat logging tests pass.
- [ ] 14.8 Pipeline logging tests pass.
- [ ] 14.9 `vnalpha logs bundle --latest` produces a usable support artifact.
- [ ] 14.10 OpenSpec tasks remain unchecked until backed by evidence.
