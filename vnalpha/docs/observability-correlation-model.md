# Correlation ID Model

## Overview

Every run in VnAlpha is associated with a **correlation ID** — a UUID that threads together all observability events (commands, errors, audit, traces, repair, deploy) emitted during that run. This lets you reconstruct a complete causal chain from a single ID.

## Unified ContextVar

VnAlpha previously had two separate `_CORRELATION_ID` ContextVars:

- `vnalpha.core.logging` — injected into structured log records
- `vnalpha.observability.context` — used by observability events

As of the `close-closed-loop-logging-gaps-100` change these are **unified**: `core.logging` delegates all reads and writes to `observability.context`. There is exactly one ContextVar that drives both subsystems.

```python
# Both of these reference the same underlying ContextVar
from vnalpha.core.logging import get_correlation_id, set_correlation_id
from vnalpha.observability.context import get_correlation_id, set_correlation_id
```

## Lifecycle

```
CLI command starts
  └─ command_lifecycle() context manager entered
       ├─ if correlation_id is "unset" → auto-generate UUID4 and set it
       ├─ log_command_start()  → COMMAND_STARTED event with correlation_id
       ├─ [command body runs]
       └─ log_command_success() or log_command_failure()
            └─ COMMAND_SUCCEEDED / COMMAND_FAILED with same correlation_id
```

Every JSONL event written within the command body inherits the same correlation ID automatically via the ContextVar.

## Setting / Reading

```python
from vnalpha.observability.context import set_correlation_id, get_correlation_id

# Start a run — auto-generates a UUID4 and sets it
cid = set_correlation_id()

# Retrieve current correlation ID
cid = get_correlation_id()   # Returns "" if unset (never returns "unset")

# Set a specific ID (e.g., from an upstream system)
set_correlation_id("f47ac10b-58cc-4372-a567-0e02b2c3d479")
```

## Propagation into Log Records

`_inject_correlation_id` is a `structlog` processor registered in `vnalpha.core.logging`. It calls `get_correlation_id()` and injects the result as the `correlation_id` field in every structured log record, whether or not you pass it explicitly.

## Cross-module Guarantee

Because `core.logging` delegates to `observability.context`:

- Setting the ID in `core.logging` is visible in `observability.context` and vice versa.
- There is no scenario where two subsystems carry different IDs for the same run.
- `asyncio.Task`-safe: the ContextVar correctly scopes to each async task.

## Event Files that Carry correlation_id

All JSONL event files contain `correlation_id`:

| File | Events |
|------|--------|
| `commands.jsonl` | COMMAND_STARTED, COMMAND_SUCCEEDED, COMMAND_FAILED |
| `errors.jsonl` | EXCEPTION_CAPTURED |
| `audit.jsonl` | all audit events |
| `trace.jsonl` | TOOL_CALL_STARTED, TOOL_CALL_SUCCEEDED, TOOL_CALL_FAILED, TOOL_CALL_REFUSED |
| `repair.jsonl` | REPAIR_PREPARED, REPAIR_STARTED, REPAIR_UPDATED, REPAIR_VALIDATED |
| `deploy.jsonl` | DEPLOY_VERIFY_*, DEPLOY_PROMOTED, DEPLOY_ROLLBACK_*, DEPLOY_SMOKE_COMPLETED |

## Querying Events by Correlation ID

```bash
# Find all events for a specific run
grep '"correlation_id": "f47ac10b"' ~/.vnalpha/logs/runs/*/commands.jsonl
grep '"correlation_id": "f47ac10b"' ~/.vnalpha/logs/runs/*/errors.jsonl

# Using vnalpha logs CLI
vnalpha logs tail --run latest
vnalpha logs summary --run latest
```
