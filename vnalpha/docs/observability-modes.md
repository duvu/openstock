# Observability Content Modes and Redaction

## Content Modes

vnalpha supports three content logging modes. The mode controls how much of the
runtime content (tool output, LLM responses, query results) is written to log files.

| Mode | Description | Use Case |
|------|-------------|----------|
| `metadata` | Only event type, timestamps, and structural metadata | Highest privacy; minimal disk usage |
| `redacted` | Metadata + sanitized content with sensitive values replaced | **Default** — balanced privacy and debuggability |
| `full` | Complete content including raw tool output and LLM responses | Debugging; requires explicit opt-in |

## Default Mode

The default mode is **`redacted`**. This means:
- Sensitive dictionary keys (tokens, keys, passwords, secrets, credentials) are replaced with `"<redacted>"`
- Sensitive-looking string values matching patterns like API keys or tokens are replaced
- Event structure and summaries are preserved

## Configuring the Mode

Set via environment variable:

```bash
# Use full content mode (for local debugging only)
VNALPHA_LOG_MODE=full vnalpha logs bundle --latest
```

Or pass `mode=` to logging helpers in Python:

```python
from vnalpha.observability.repair import log_repair_event

log_repair_event("REPAIR_PREPARED", "Bundle created", repair_id="r001", mode="full")
```

## Redacted Keys

The following key names are always redacted in dictionary payloads:
`token`, `api_key`, `password`, `secret`, `credential`, `private_key`, `access_token`,
`refresh_token`, `client_secret`, `auth`, `authorization`.

## Redacted Value Patterns

String values matching these patterns are redacted:
- Patterns resembling API keys (long alphanumeric strings with underscores)
- Patterns matching `Bearer <token>`

## Opting Into Full Mode

Full mode writes raw content. Only use it:
- On a local development machine
- When you explicitly need LLM response bodies or tool output for debugging
- Never in production or shared log storage

Full mode is never the default and is never applied automatically.

## Bundles and AI Coding Prompts

Repair bundles (`vnalpha repair prepare`) always apply at least `redacted` mode
when copying JSONL files into `raw-logs/`. Secret files (`.env`, `.pem`, `.key`,
`secrets*`) are always excluded regardless of mode.
