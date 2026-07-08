# Review: File-based observability for AI-agent-readable logs

## Current finding

OpenStock already has several persistence and verification surfaces, but they are optimized for domain state or manual validation rather than AI-agent-readable operational history.

Relevant existing surfaces:

```text
chat_session / chat_message        persistent chat transcript
trace-related helpers              tool lifecycle linkage for chat paths
CommandExecutor                    shared command execution path
openstock-verify                   deploy verification script
openstock-run-pipeline             daily pipeline wrapper
vnalpha tests and validation docs   completion evidence
```

These are valuable, but they do not yet provide a unified file-based activity trail that can be bundled and handed to an AI agent.

## Problem patterns observed

### 1. Operational evidence is scattered

Evidence is currently split across console output, validation markdown, DuckDB tables, shell script output, and test logs. An AI agent must infer too much from many unrelated locations.

### 2. Some failures are intentionally swallowed

Several UI and best-effort paths avoid crashing by catching exceptions. This is acceptable for user experience, but every swallowed exception should still produce a structured error event.

### 3. Console output is not enough

A human can read console output during execution, but an AI agent needs stable files after execution. Plain console logs do not reliably provide event IDs, correlation IDs, run IDs, status transitions, output tails, or source module names.

### 4. Audit and debug logs should not be mixed

Activity/audit events should be queryable without reading every debug message. App logs can be noisy; audit events must remain semantically meaningful.

### 5. AI-agent context must be curated

Large raw logs are expensive for agents to read. Each run should produce a short `ai-agent-summary.md` that points to the raw JSONL files only when needed.

## Recommended direction

Use a hybrid file layout:

```text
JSONL raw logs      machine-readable source of truth
Markdown summary    AI-first entrypoint
JSON schemas        stable event contracts
bundle command      portable support artifact
```

The first implementation should prioritize file durability and parseability over a centralized observability stack.

## Proposed completion estimate after implementation

If fully implemented, this change should move the system from ad-hoc operational evidence to structured local observability:

```text
AI-agent log readability:       20-30% -> 85-90%
Runtime failure diagnosability: 50-60% -> 85-90%
Audit trail consistency:        55-65% -> 85-90%
Developer handoff quality:      40-50% -> 85-90%
```

## Risks

### Log volume

JSONL files can grow quickly. The implementation needs retention, rotation, or at least documented cleanup.

### Sensitive content

Prompt, answer, tool output, command output, and environment data may include sensitive runtime values. Default logging must be redacted and configurable.

### Over-instrumentation

Logging every trivial UI state change may create noise. The initial implementation should focus on meaningful workflow events and errors.

### Partial write failures

Logging must not crash the core workflow. File write errors should degrade gracefully and be reported to stderr when possible.

### Agent misinterpretation

The `ai-agent-summary.md` must distinguish between observed facts, likely causes, and suggested next steps. It should not present guesses as confirmed root causes.

## Open questions

- Should log root default to `/var/log/openstock` for package installs and `~/.local/state/openstock/logs` for local dev?
- Should TUI sessions create one run directory per app launch or one per chat session?
- Should full prompt/answer logging be allowed only through an explicit opt-in environment variable?
- Should `logs bundle` include DuckDB snapshots, or only text logs?
- Should shell scripts write JSONL directly or call a small Python helper?
- Should retention be implemented now or deferred to a later change?
