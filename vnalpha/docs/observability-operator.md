# Observability Operator Guide — Collecting Logs for AI Agents

## Purpose

This guide explains how to collect, inspect, and hand off vnalpha run logs to an AI coding or review agent.

## Quick start

```bash
vnalpha logs latest          # Print path to latest run
vnalpha logs show --latest   # Pretty-print recent app events
vnalpha logs errors --latest # Show recent errors and warnings
vnalpha logs summarize --latest  # Regenerate ai-agent-summary.md
vnalpha logs doctor --latest     # Health check: any missing files or errors?
vnalpha logs bundle --latest     # Create a portable .tar.gz artifact
```

## Handing logs to an AI agent

The recommended workflow:

1. Run `vnalpha logs bundle --latest` to create a `.tar.gz` bundle.
2. The bundle contains:
   - `run/ai-agent-summary.md` — the AI-readable narrative (start here)
   - `run/errors.jsonl` — all exceptions and warnings
   - `run/commands.jsonl` — command history with exit codes and timing
   - `run/trace.jsonl` — workflow/tool timeline
   - `run/audit.jsonl` — activity trail
   - `run/environment.json` — git branch/commit, Python, platform
   - `schemas/` — JSON schemas for all event types
3. Give the bundle to the AI agent. Ask it to:
   - Read `ai-agent-summary.md` first.
   - Use `errors.jsonl` for stack trace investigation.
   - Cross-reference `correlation_id` across files to reconstruct workflows.

## Correlation ID reconstruction

To find all events for a specific workflow:

```bash
grep '"correlation_id": "abc123"' ~/.local/state/openstock/logs/runs/latest/*.jsonl
```

Or in Python:
```python
import json
from pathlib import Path

run_dir = Path.home() / ".local/state/openstock/logs/runs/latest"
cid = "abc123"
for fname in ["audit.jsonl", "commands.jsonl", "errors.jsonl", "trace.jsonl"]:
    path = run_dir / fname
    if path.exists():
        for line in path.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("correlation_id") == cid:
                print(fname, rec)
```

## Content modes

By default, sensitive values (passwords, tokens, API keys) are replaced with `[REDACTED]`.

To enable full content logging for local debugging:
```bash
VNALPHA_LOG_CONTENT_MODE=full vnalpha ask "..."
```

**Never enable full mode in shared/deployed environments.**

## Log root override

```bash
VNALPHA_LOG_ROOT=/tmp/debug-logs vnalpha sync symbols
vnalpha logs latest
```

## Generating a fresh summary

If you've added more events to a run directory, regenerate the summary:
```bash
vnalpha logs summarize --run-id cli_20260708T123456_abc12345
```

## AI agent investigation checklist

When handing a bundle to an AI agent, suggest these steps:

1. Read `ai-agent-summary.md` for overall status.
2. Look at `errors.jsonl` for stack traces — check `stacktrace_hash` for repeats.
3. Check `commands.jsonl` for failed commands (`"status": "FAILED"`).
4. In `trace.jsonl`, find slow operations (`duration_ms > 5000`).
5. In `audit.jsonl`, find the correlation_id of the relevant workflow.
6. Cross-reference that correlation_id across all JSONL files.
7. Check `environment.json` for git branch/commit to find relevant source code.

## Schema reference

All JSONL event schemas are in `observability/schemas/`:
- `audit-event.schema.json`
- `app-log.schema.json`
- `error-event.schema.json`
- `trace-event.schema.json`
- `command-event.schema.json`

## Retention assumptions

- Runs are never automatically deleted.
- Each run directory is typically 1–50 KB.
- For long-running deployments, set up a cron to remove runs older than 30 days.

## Example: investigate a failed sync

```bash
vnalpha sync symbols
vnalpha logs errors --latest
```

Look for `SYNC_FAILED` in errors.jsonl. Check `stacktrace` and `likely_cause`.
Then run:
```bash
vnalpha logs summarize --latest
```
to get a full narrative with suggested investigation steps.
