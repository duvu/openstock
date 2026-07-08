# JSONL Event Examples

> Representative examples of each event type written by the vnalpha observability system.
> All files are newline-delimited JSON (one object per line).

---

## audit.jsonl

```json
{"ts":"2026-07-08T10:30:45Z","event_type":"CLI_STARTED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","summary":"CLI surface started","level":"INFO","module":"vnalpha.cli"}
{"ts":"2026-07-08T10:30:46Z","event_type":"WAREHOUSE_MIGRATION_STARTED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","summary":"Warehouse migration started: warehouse","level":"INFO","module":"vnalpha.warehouse.migrations"}
{"ts":"2026-07-08T10:30:47Z","event_type":"WAREHOUSE_MIGRATION_RUN","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","summary":"Warehouse migration succeeded: warehouse","level":"INFO","module":"vnalpha.warehouse.migrations"}
{"ts":"2026-07-08T10:30:48Z","event_type":"FEATURE_BUILD_COMPLETE","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","summary":"Feature build complete date=2026-07-07 built=42 skipped=3","level":"INFO","module":"vnalpha.features.build_features"}
{"ts":"2026-07-08T10:30:49Z","event_type":"PLAN_APPROVED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"3e8a1c52-9f4b-4d7e-b123-1a2b3c4d5e6f","summary":"User approved plan","level":"INFO","module":"vnalpha.chat.controller"}
{"ts":"2026-07-08T10:30:50Z","event_type":"PLAN_CANCELLED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"3e8a1c52-9f4b-4d7e-b123-1a2b3c4d5e6f","summary":"User cancelled plan","level":"INFO","module":"vnalpha.chat.controller"}
{"ts":"2026-07-08T10:30:51Z","event_type":"PLAN_PREVIEWED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"7c9f2d84-1e3b-4a5c-8d7e-9f0a1b2c3d4e","summary":"Plan previewed with 3 step(s)","level":"INFO","module":"vnalpha.chat.controller"}
{"ts":"2026-07-08T10:30:52Z","event_type":"CHAT_REFUSAL","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"7c9f2d84-1e3b-4a5c-8d7e-9f0a1b2c3d4e","summary":"Refusal: Tool 'order.place' is permanently forbidden.","level":"WARNING","module":"vnalpha.chat.controller"}
{"ts":"2026-07-08T10:30:53Z","event_type":"TOOL_REFUSED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"7c9f2d84-1e3b-4a5c-8d7e-9f0a1b2c3d4e","summary":"Tool 'order.place' refused: requires permission EXECUTE_TRADE","level":"WARNING","module":"vnalpha.tools"}
```

---

## errors.jsonl

```json
{"ts":"2026-07-08T10:30:55Z","event_type":"EXCEPTION","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","level":"ERROR","error_type":"ConnectionError","message":"Connection refused at http://127.0.0.1:6900","module":"vnalpha.warehouse.connection","function":"_connect","stacktrace":"Traceback (most recent call last):\n  File \"/usr/lib/vnalpha/warehouse/connection.py\", line 42, in _connect\n    raise ConnectionError(...)","stacktrace_hash":"a1b2c3d4","likely_cause":"vnstock-service not running","suggested_next_step":"Run: docker compose up vnstock-service"}
{"ts":"2026-07-08T10:30:56Z","event_type":"DATA_QUALITY_WARNING","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","level":"WARNING","error_type":"DataQualityWarning","message":"Missing benchmark data for VNINDEX on 2026-07-07","module":"vnalpha.features","function":"build_features"}
```

---

## commands.jsonl

```json
{"ts":"2026-07-08T10:30:45Z","event_type":"COMMAND_STARTED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","command":"vnalpha build features --date 2026-07-07","status":"STARTED","exit_code":null,"duration_ms":null,"stdout_tail":"","stderr_tail":""}
{"ts":"2026-07-08T10:30:53Z","event_type":"COMMAND_COMPLETED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","command":"vnalpha build features --date 2026-07-07","status":"SUCCESS","exit_code":0,"duration_ms":8312.4,"stdout_tail":"[OK] Built features for 42 symbols","stderr_tail":""}
{"ts":"2026-07-08T10:35:12Z","event_type":"COMMAND_FAILED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"b8e2f49d-3c1a-4e7f-9d5b-2e3f4a5b6c7d","command":"vnalpha sync ohlcv --universe VN30 --start 2024-01-01","status":"FAILED","exit_code":1,"duration_ms":3201.0,"stdout_tail":"","stderr_tail":"ConnectionError: Connection refused at http://127.0.0.1:6900"}
```

---

## trace.jsonl

```json
{"ts":"2026-07-08T10:30:49Z","event_type":"TOOL_CALL_STARTED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"3e8a1c52-9f4b-4d7e-b123-1a2b3c4d5e6f","span_id":"sp_01j5x8k2m3n4p5q6r7s8t9u0","parent_span_id":"","name":"watchlist.scan","status":"RUNNING","duration_ms":null,"module":"vnalpha.tools"}
{"ts":"2026-07-08T10:30:49Z","event_type":"TOOL_CALL_SUCCEEDED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"3e8a1c52-9f4b-4d7e-b123-1a2b3c4d5e6f","span_id":"sp_01j5x8k2m3n4p5q6r7s8t9u0","parent_span_id":"","name":"watchlist.scan","status":"SUCCESS","duration_ms":142.3,"module":"vnalpha.tools"}
{"ts":"2026-07-08T10:30:50Z","event_type":"TOOL_CALL_FAILED","run_id":"cli_20260708T103045_a1b2c3d4","correlation_id":"7c9f2d84-1e3b-4a5c-8d7e-9f0a1b2c3d4e","span_id":"sp_01j5x8k2m3n4p5q6r7s8t9u1","parent_span_id":"","name":"ohlcv.fetch","status":"FAILED","duration_ms":3180.0,"module":"vnalpha.tools"}
```

---

## environment.json

```json
{
  "run_id": "cli_20260708T103045_a1b2c3d4",
  "ts": "2026-07-08T10:30:45Z",
  "git_branch": "main",
  "git_commit": "264975f",
  "git_dirty": false,
  "python": "3.12.3",
  "platform": "Linux-6.8.0-x86_64-with-glibc2.39",
  "vnalpha_version": "0.1.0",
  "log_content_mode": "redacted",
  "surface": "cli",
  "actor": "beou"
}
```

---

## Cross-referencing with correlation_id

All events within the same logical workflow share a `correlation_id`. To reconstruct a workflow timeline:

```bash
CID="f47ac10b-58cc-4372-a567-0e02b2c3d479"
grep "$CID" ~/.local/state/openstock/logs/runs/latest/*.jsonl | sort -k1
```

Or in Python:
```python
import json
from pathlib import Path

run_dir = Path.home() / ".local/state/openstock/logs/runs/latest"
cid = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
events = []
for fname in sorted(run_dir.glob("*.jsonl")):
    for line in fname.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("correlation_id") == cid:
            events.append((rec["ts"], fname.name, rec["event_type"], rec.get("summary", "")))
for ev in sorted(events):
    print(*ev, sep="\t")
```
