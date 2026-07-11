# Proposal: File-based observability and closed-loop AI repair workflow

## Summary

Add an OpenSpec change for a file-first observability layer and a closed-loop AI repair workflow.

The intended loop is:

```text
System runs and interacts with users
  -> logs activities, warnings, errors, traces, commands, and deploy events
  -> packages logs into an AI-readable evidence bundle
  -> AI coding agent reads the bundle and proposes/implements a fix
  -> tests and verification gates run
  -> fix is deployed or rejected
  -> deployment result is logged
  -> the next runtime cycle continues with better evidence
```

The primary consumer is an AI coding/review agent that can inspect recent runtime behavior and improve OpenStock without needing direct access to DuckDB internals, systemd journals, or an external observability stack.

This is an OpenSpec-only change. It defines requirements and validation gates; it does not implement the logging or repair loop yet.

## Why

OpenStock is becoming a terminal-first, local-first research system with CLI, TUI, ChatController, pipeline scripts, package checks, deploy checks, and worker jobs. As the codebase grows, failures are increasingly distributed across CLI entrypoints, TUI screens, ChatController, AssistantApp, CommandExecutor, tool execution, DuckDB migrations, pipeline wrappers, systemd units, packaging scripts, and backup scripts.

The current logging approach is useful while watching a console, but it is not yet a durable structured artifact that another process can inspect later.

OpenStock needs logs that answer:

- what command ran;
- what the user did;
- which workflow or session it belonged to;
- which step failed;
- what warnings preceded the failure;
- what files or modules were involved;
- what deploy version was running;
- what test/deploy gate last passed or failed;
- whether sensitive content was redacted;
- what next investigation steps are likely useful.

## Problem statement

OpenStock needs a repeatable logging and repair contract that creates AI-readable files for audit, development support, and controlled redeployment.

The first implementation SHALL NOT require ELK, Loki, OpenSearch, Grafana, OpenTelemetry Collector, or any cloud logging service. Those may be future export targets, but the base layer must work locally and offline.

## Goals

- Write structured logs to files by default.
- Make logs easy for AI agents to parse, filter, summarize, and correlate.
- Preserve important activity and audit events separately from noisy app logs.
- Capture errors, warnings, stack traces, command output tails, and workflow state.
- Capture command, pipeline, chat, plan, and tool execution flows using correlation IDs.
- Generate a concise `ai-agent-summary.md` per run or session.
- Generate an AI coding handoff bundle containing logs, summaries, environment metadata, failing commands, and suggested reproduction steps.
- Enable an AI coding agent to create a fix branch or draft PR from evidence.
- Require tests, verification, and deploy gates before any fix is applied.
- Log the repair attempt, test result, deploy result, and rollback decision.
- Keep the design local-first and compatible with the current terminal-first POC.

## Non-goals

- No external log collector requirement.
- No mandatory centralized observability platform.
- No cloud logging dependency.
- No autonomous production deployment without an explicit gate.
- No self-modifying runtime process.
- No bypass of tests, code review, or rollback checks.
- No broker, order, account, portfolio, margin, transfer, or trading execution feature.
- No user-behavior analytics product.
- No replacement for DuckDB domain tables such as `chat_message`, `tool_trace`, or outcome tables.
- No guarantee that full prompt, answer, or tool output content is logged by default.
- No production multi-user compliance archive in this change.

## Scope

### File-first log layout

Add a standard log directory layout:

```text
logs/
├── latest -> runs/<run-id>/
├── runs/
│   └── <run-id>/
│       ├── audit.jsonl
│       ├── app.jsonl
│       ├── errors.jsonl
│       ├── trace.jsonl
│       ├── commands.jsonl
│       ├── ai-agent-summary.md
│       ├── environment.json
│       └── README.md
├── bundles/
│   └── <bundle-id>/
│       ├── ai-agent-summary.md
│       ├── ai-coding-prompt.md
│       ├── reproduction.md
│       ├── raw-logs/
│       ├── environment.json
│       └── manifest.json
└── schemas/
    ├── audit-event.schema.json
    ├── app-log.schema.json
    ├── error-event.schema.json
    ├── trace-event.schema.json
    ├── command-event.schema.json
    ├── repair-event.schema.json
    └── deploy-event.schema.json
```

The default root path SHALL be configurable, but the internal run and bundle layout must be stable.

### Structured JSONL events

Each JSONL line SHALL be a complete JSON object. Events SHALL include stable fields such as:

```text
event_id
run_id
created_at
level
event_type
surface
actor
correlation_id
session_id
status
summary
module
function
command
exit_code
duration_ms
metadata
redaction_status
```

Error events SHALL additionally include error type, error message, stack trace, stack trace hash, likely cause, and suggested next step when available.

Repair/deploy events SHALL additionally include fix branch, PR number, commit SHA, test command, test result, deploy target, deploy status, previous version, new version, and rollback status where available.

### AI-agent summary and coding prompt

Each run or session SHALL generate or update `ai-agent-summary.md` with run metadata, what happened, errors, warnings, failed commands, suspicious patterns, likely involved files/modules, suggested investigation, and pointers to raw JSONL files.

Each bundle SHALL include `ai-coding-prompt.md` with enough context for a coding agent to reproduce, inspect, implement, test, and propose a fix.

### Closed-loop workflow

Add commands or equivalent scripts for:

```text
vnalpha logs latest
vnalpha logs show --latest
vnalpha logs errors --latest
vnalpha logs bundle --latest
vnalpha logs summarize --latest
vnalpha logs doctor --latest
vnalpha repair prepare --latest
vnalpha repair status <repair-id>
vnalpha repair validate <repair-id>
vnalpha deploy verify
vnalpha deploy promote <candidate>
vnalpha deploy rollback <deployment-id>
```

The exact names may change, but these functions must exist.

### Correlation model

Every high-level flow SHALL have a `correlation_id`. Related audit, trace, command, app, error, repair, and deploy events SHALL reuse the same correlation ID.

Required correlated flows include CLI command execution, TUI session, ChatController turn, pipeline run, pipeline step, tool call group, verify run, package run, backup run, restore run, repair attempt, test run, deploy attempt, and rollback attempt.

### Redaction model

The system SHALL redact sensitive runtime values by default. Prompt, answer, tool-output, environment, command-output, bundle, and AI coding prompt content SHALL be configurable with at least these modes:

```text
metadata
redacted
full
```

Default SHALL be `redacted` or safer.

### Instrumentation points

Initial implementation SHALL instrument at least:

```text
CLI entrypoint
CommandExecutor
ChatController
AssistantApp.ask
LocalToolRegistry / tool executor
pipeline wrapper
openstock-verify
backup/restore scripts
warehouse migration runner
data sync
feature build
scoring
watchlist generation
outcome evaluation
TUI app/screen lifecycle errors
repair preparation command
test/validation runner
deploy verification command
deploy promote/rollback scripts
```

## Success criteria

This change is complete only when:

```text
make test-vnalpha passes
make lint-vnalpha passes or exceptions are explicitly documented
structured JSONL logs are written for CLI command runs
errors.jsonl captures exceptions with redacted stack traces
commands.jsonl captures command status, duration, exit code, and output tails
trace.jsonl captures correlated workflow/tool steps
ChatController emits log events for prompt, answer/refusal, plan preview, approval, cancellation, and runtime error
pipeline wrapper emits pipeline and step events
openstock-verify emits verify events
ai-agent-summary.md is generated for each run/session
schemas are committed for every JSONL event type
redaction tests pass
correlation_id tests pass
log bundle command produces a portable AI-readable evidence artifact
repair prepare command creates an AI coding prompt and manifest from latest logs
repair events record proposed fix branch/PR/test/deploy state
deploy verification records previous version, candidate version, result, and rollback path
OpenSpec tasks are not marked complete without code/test/script evidence
```

## Completion principle

Do not treat console logging as sufficient. A task is complete only when the event is written to a documented file format and can be consumed later by another process or AI agent.

Do not treat AI repair as complete until the fix is validated by tests, deploy verification, and recorded repair/deploy events. The loop may be AI-assisted, but it must remain evidence-gated.
