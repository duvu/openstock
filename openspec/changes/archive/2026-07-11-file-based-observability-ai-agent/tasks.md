# Tasks: File-based observability and closed-loop AI repair workflow

## 0. Completion governance

- [x] 0.1 Treat this change as an implementation requirement for file-based observability and controlled AI repair, not a docs-only completion claim.
- [x] 0.2 Do not mark tasks complete until code, tests, scripts, or validation logs exist.
- [x] 0.3 Keep `review.md` updated if implementation findings change.
- [x] 0.4 Add validation evidence when implementation PRs run tests or scripts.
- [x] 0.5 Document any intentionally deferred tasks with reason and owner.
- [x] 0.6 Do not allow AI-assisted repair to bypass tests, review, deploy verification, or rollback checks.

## 1. Log directory and run model

- [x] 1.1 Add configurable log root resolution.
- [x] 1.2 Use `/var/log/openstock` for packaged/deployed mode when writable.
- [x] 1.3 Use `~/.local/state/openstock/logs` as local fallback.
- [x] 1.4 Add run directory creation under `runs/<run-id>/`.
- [x] 1.5 Add `latest` symlink or `latest.txt` pointer fallback.
- [x] 1.6 Write `environment.json` with branch/commit/python/platform/config summary where available.
- [x] 1.7 Write per-run `README.md` explaining file meanings.
- [x] 1.8 Add tests for run directory creation and latest pointer behavior.

## 2. JSONL sink and schemas

- [x] 2.1 Add JSONL append helper that writes one valid JSON object per line.
- [x] 2.2 Ensure writer creates parent directories.
- [x] 2.3 Ensure writer is best-effort and does not crash core workflows.
- [x] 2.4 Add schema definitions for audit events.
- [x] 2.5 Add schema definitions for app log events.
- [x] 2.6 Add schema definitions for error events.
- [x] 2.7 Add schema definitions for trace events.
- [x] 2.8 Add schema definitions for command events.
- [x] 2.9 Add schema definitions for repair events.
- [x] 2.10 Add schema definitions for deploy events.
- [x] 2.11 Commit schema JSON files or generated schema docs.
- [x] 2.12 Add tests proving JSONL lines parse as valid JSON.
- [x] 2.13 Add tests proving required fields are present.

## 3. Redaction and content policy

- [x] 3.1 Add redaction module for sensitive runtime values.
- [x] 3.2 Redact sensitive keys in dictionaries before writing logs.
- [x] 3.3 Redact sensitive-looking values in strings before writing logs.
- [x] 3.4 Add configurable content mode: `metadata`, `redacted`, `full`.
- [x] 3.5 Default content mode to `redacted` or safer.
- [x] 3.6 Ensure `full` mode requires explicit opt-in.
- [x] 3.7 Apply redaction to logs, summaries, bundles, and AI coding prompts.
- [x] 3.8 Add tests for dictionary redaction.
- [x] 3.9 Add tests for string redaction.
- [x] 3.10 Add tests proving default mode does not write unredacted sensitive values.

## 4. Correlation and context propagation

- [x] 4.1 Add run context object containing `run_id`, surface, actor, and log paths.
- [x] 4.2 Add correlation context object containing `correlation_id` and optional parent span.
- [x] 4.3 Generate a new correlation ID for each CLI command execution.
- [x] 4.4 Generate a new correlation ID for each ChatController turn.
- [x] 4.5 Generate a new correlation ID for each pipeline run.
- [x] 4.6 Generate a new correlation ID for each repair attempt.
- [x] 4.7 Generate a new correlation ID for each deploy or rollback attempt.
- [x] 4.8 Generate child span IDs for pipeline steps and tool calls.
- [x] 4.9 Propagate correlation ID to audit, command, trace, app, error, repair, and deploy events.
- [x] 4.10 Add tests proving related events share a correlation ID.

## 5. CLI and command logging

- [x] 5.1 Instrument the main CLI entrypoint.
- [x] 5.2 Write command start event to `commands.jsonl`.
- [x] 5.3 Write command success event to `commands.jsonl`.
- [x] 5.4 Write command failure event to `commands.jsonl`.
- [x] 5.5 Capture `duration_ms`.
- [x] 5.6 Capture `exit_code` when available.
- [x] 5.7 Capture bounded stdout/stderr tails when available.
- [x] 5.8 Write high-level command audit event to `audit.jsonl`.
- [x] 5.9 Instrument `CommandExecutor` so TUI/chat commands are also logged.
- [x] 5.10 Add tests for CLI command success and failure log events.

## 6. Error and warning logging

- [x] 6.1 Add centralized exception capture helper.
- [x] 6.2 Write exceptions to `errors.jsonl`.
- [x] 6.3 Include error type, message, module, function, stack trace, and stack trace hash.
- [x] 6.4 Include likely cause only when deterministic or explicitly inferred.
- [x] 6.5 Include suggested next step when useful.
- [x] 6.6 Instrument currently best-effort `except Exception` paths to log before swallowing.
- [x] 6.7 Log warnings for degraded behavior and skipped validations.
- [x] 6.8 Add tests for error capture.
- [x] 6.9 Add tests proving logging failure does not crash the original workflow.

## 7. ChatController and assistant logging

- [x] 7.1 Log `CHAT_TURN_STARTED` for each ChatController natural-language turn.
- [x] 7.2 Log user prompt metadata according to content mode.
- [x] 7.3 Log `PLAN_PREVIEWED` when a plan is generated.
- [x] 7.4 Log `PLAN_APPROVED` when a plan is approved.
- [x] 7.5 Log `PLAN_CANCELLED` when a plan is cancelled.
- [x] 7.6 Log assistant answer metadata according to content mode.
- [x] 7.7 Log assistant refusal as audit and error/warning when appropriate.
- [x] 7.8 Log ChatController runtime errors to `errors.jsonl`.
- [x] 7.9 Instrument `AssistantApp.ask` with trace events.
- [x] 7.10 Add tests for chat turn logging.
- [x] 7.11 Add tests for plan lifecycle logging.
- [x] 7.12 Add tests for refusal logging.

## 8. Tool and trace logging

- [x] 8.1 Instrument LocalToolRegistry or equivalent tool execution path.
- [x] 8.2 Write `TOOL_CALL_STARTED` trace events.
- [x] 8.3 Write `TOOL_CALL_SUCCEEDED` trace events.
- [x] 8.4 Write `TOOL_CALL_FAILED` trace events.
- [x] 8.5 Write `TOOL_REFUSED` audit events for denied tools.
- [x] 8.6 Include tool name, status, duration, correlation ID, and parent span.
- [x] 8.7 Do not log full tool output unless content mode allows it.
- [x] 8.8 Add tests for successful tool trace.
- [x] 8.9 Add tests for failed tool trace.
- [x] 8.10 Add tests for refused tool audit.

## 9. Pipeline, verify, and backup script logging

- [x] 9.1 Instrument `openstock-run-pipeline` with run start/completion events.
- [x] 9.2 Log each pipeline step start/success/failure.
- [x] 9.3 Include command text, duration, status, and output tail for each step.
- [x] 9.4 Instrument `openstock-verify` with verify check events.
- [x] 9.5 Instrument `openstock-backup-warehouse` with backup events.
- [x] 9.6 Add restore logging if restore script exists or is added later.
- [x] 9.7 Ensure shell-script logging writes valid JSONL.
- [x] 9.8 Add shell/static tests for JSONL syntax or helper invocation.

## 10. Data pipeline domain logging

- [x] 10.1 Log warehouse migration start/success/failure.
- [x] 10.2 Log data sync start/success/failure.
- [x] 10.3 Log feature build start/success/failure and row counts.
- [x] 10.4 Log scoring start/success/failure and candidate counts.
- [x] 10.5 Log watchlist generation start/success/failure and selected counts.
- [x] 10.6 Log outcome evaluation start/success/failure and evaluation counts.
- [x] 10.7 Log data quality warnings.
- [x] 10.8 Add tests for at least one success and one failure path per major domain group.

## 11. AI-agent summary

- [x] 11.1 Add summary generator for `ai-agent-summary.md`.
- [x] 11.2 Summarize run metadata.
- [x] 11.3 Summarize what happened.
- [x] 11.4 Summarize errors and warnings.
- [x] 11.5 Summarize failed commands.
- [x] 11.6 Summarize suspicious patterns.
- [x] 11.7 List likely involved files or modules.
- [x] 11.8 List suggested investigation steps.
- [x] 11.9 Link raw JSONL files.
- [x] 11.10 Distinguish observed facts from likely causes.
- [x] 11.11 Add tests for summary generation.

## 12. Log commands and bundle

- [x] 12.1 Add `vnalpha logs latest` or equivalent.
- [x] 12.2 Add `vnalpha logs show --latest` or equivalent.
- [x] 12.3 Add `vnalpha logs errors --latest` or equivalent.
- [x] 12.4 Add `vnalpha logs summarize --latest` or equivalent.
- [x] 12.5 Add `vnalpha logs doctor --latest` or equivalent.
- [x] 12.6 Add `vnalpha logs bundle --latest` or equivalent.
- [x] 12.7 Ensure bundle excludes unsafe files by default.
- [x] 12.8 Ensure bundle contains summary, JSONL logs, schemas, and environment summary.
- [x] 12.9 Add tests for logs command group.
- [x] 12.10 Add tests for bundle output.

## 13. Closed-loop AI repair preparation

- [x] 13.1 Add `vnalpha repair prepare --latest` or equivalent.
- [x] 13.2 Create a repair bundle under `bundles/<bundle-id>/`.
- [x] 13.3 Generate `ai-coding-prompt.md` from the latest logs.
- [x] 13.4 Generate `reproduction.md` with exact failing commands and expected/actual behavior.
- [x] 13.5 Generate `manifest.json` listing included files, redaction mode, source run IDs, commit SHA, and generated timestamp.
- [x] 13.6 Include top errors, warnings, failed commands, suspicious patterns, and likely modules.
- [x] 13.7 Include test commands the coding agent must run.
- [x] 13.8 Include explicit guardrails: no broker/order/account/portfolio/trading execution features.
- [x] 13.9 Add tests for repair bundle generation.
- [x] 13.10 Add tests proving unsafe files/secrets are excluded or redacted.

## 14. AI repair execution tracking

- [x] 14.1 Add repair event type family to `audit.jsonl` or `repair.jsonl`.
- [x] 14.2 Log `REPAIR_PREPARED` when a bundle is generated.
- [x] 14.3 Log `REPAIR_STARTED` when an AI coding agent starts work, if integrated.
- [x] 14.4 Log proposed fix branch name.
- [x] 14.5 Log proposed PR number or URL when available.
- [x] 14.6 Log commit SHA(s) involved in the fix.
- [x] 14.7 Log validation commands requested by the bundle.
- [x] 14.8 Log validation results.
- [x] 14.9 Log whether repair was accepted, rejected, or deferred.
- [x] 14.10 Add `vnalpha repair status <repair-id>` or equivalent.
- [x] 14.11 Add `vnalpha repair validate <repair-id>` or equivalent.
- [x] 14.12 Add tests for repair status and validation logging.

## 15. Deploy, promote, and rollback loop

- [x] 15.1 Add deploy event type family to `audit.jsonl` or `deploy.jsonl`.
- [x] 15.2 Add `vnalpha deploy verify` or equivalent.
- [x] 15.3 Add `vnalpha deploy promote <candidate>` or equivalent, or document existing deployment script integration.
- [x] 15.4 Add `vnalpha deploy rollback <deployment-id>` or equivalent, or document existing rollback script integration.
- [x] 15.5 Log previous deployed version before promotion.
- [x] 15.6 Log candidate version before promotion.
- [x] 15.7 Require tests and verification gates before promotion.
- [x] 15.8 Log deployment result.
- [x] 15.9 Log post-deploy smoke result.
- [x] 15.10 Log rollback availability.
- [x] 15.11 Log rollback result when rollback is executed.
- [x] 15.12 Add tests or static validation for deploy event generation.

## 16. Closed-loop end-to-end scenario

- [x] 16.1 Add a documented scenario: runtime failure -> logs -> bundle -> AI coding prompt -> fix branch/PR -> tests -> deploy verify -> promote -> post-deploy logs.
- [x] 16.2 Add a fixture-based failed command that generates an error bundle.
- [x] 16.3 Add a test proving `repair prepare` can consume the failed run and generate a usable bundle.
- [x] 16.4 Add a test or dry-run proving deployment promotion is blocked when validation fails.
- [x] 16.5 Add a test or dry-run proving deployment promotion records result when validation passes.
- [x] 16.6 Add docs explaining which steps are automatic, AI-assisted, and human-gated.

## 17. Documentation and validation

- [x] 17.1 Add developer docs explaining log layout.
- [x] 17.2 Add operator docs explaining how to collect logs for an AI agent.
- [x] 17.3 Document content logging modes and redaction behavior.
- [x] 17.4 Document retention/cleanup assumptions.
- [x] 17.5 Document closed-loop AI repair workflow.
- [x] 17.6 Document deploy promotion and rollback gates.
- [x] 17.7 Add validation report with command outputs.
- [x] 17.8 Add examples of `ai-agent-summary.md`.
- [x] 17.9 Add examples of `ai-coding-prompt.md`.
- [x] 17.10 Add examples of JSONL event lines.

## 18. Acceptance gates

- [x] 18.1 `make test-vnalpha` passes.
- [x] 18.2 `make lint-vnalpha` passes or exceptions are documented.
- [x] 18.3 Redaction tests pass.
- [x] 18.4 JSONL schema/parse tests pass.
- [x] 18.5 Correlation propagation tests pass.
- [x] 18.6 CLI command logging tests pass.
- [x] 18.7 Chat logging tests pass.
- [x] 18.8 Pipeline logging tests pass.
- [x] 18.9 `vnalpha logs bundle --latest` produces a usable support artifact.
- [x] 18.10 `vnalpha repair prepare --latest` produces a usable AI coding bundle.
- [x] 18.11 Repair status/validation logs are written.
- [x] 18.12 Deploy verify/promote/rollback dry-run events are written.
- [x] 18.13 OpenSpec tasks remain unchecked until backed by evidence.
