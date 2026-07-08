# Example: ai-coding-prompt.md

This is an example of the `ai-coding-prompt.md` file generated inside a repair bundle by `vnalpha repair prepare --latest`.

---

# AI Coding Prompt — Repair Bundle `repair_001`

Generated: 2024-01-15T08:23:41+00:00  
Source run: `run_20240115T082301_abc12345`  
Commit: `abc1234` on branch `main`

---

## Task

Fix the runtime failure captured in run `run_20240115T082301_abc12345`.

The system failed during feature computation. The error was captured and summarized below.
Your job is to identify the root cause and produce a minimal fix.

---

## Error Summary

**Top error:**
```
ZeroDivisionError: division by zero
  Module: vnalpha.features.compute
  Function: compute_rsi
  Count: 1
```

**Failed commands:**
- `make build-features` exited with code 1

---

## Files to Investigate

Based on the error module path:
- `vnalpha/features/compute.py`
- `vnalpha/features/__init__.py`

---

## Reproduction Steps

See `reproduction.md` for the exact commands to reproduce the failure.

---

## Required Test Commands

After implementing your fix, you MUST run all of the following and ensure they pass:

```bash
cd vnalpha && make test-vnalpha
cd vnalpha && make lint-vnalpha
```

Use `vnalpha repair validate repair_001` to record the validation result.

---

## Required guardrails

**DO NOT** add, modify, or enable any of:
- Broker connectivity or order execution
- Account, portfolio, or position management features
- Trading signal execution or live-order routing
- Any feature that interacts with live financial market APIs beyond read-only data

All changes must remain in data/analysis/observability scope only.

---

## Raw Logs

Raw JSONL event files are in `raw-logs/`:
- `raw-logs/errors.jsonl` — captured exceptions
- `raw-logs/commands.jsonl` — command executions
- `raw-logs/audit.jsonl` — audit trail

All files have been redacted (mode: `redacted`). No secrets are included.

---

## Environment

```json
{
  "python": "3.12.3",
  "branch": "main",
  "commit": "abc1234",
  "platform": "linux"
}
```
