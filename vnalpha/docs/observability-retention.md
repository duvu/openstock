# Observability Log Retention and Cleanup

## Assumptions

vnalpha uses a simple file-based log layout with no automatic rotation or expiry.
Operators are responsible for cleanup. These are the working assumptions:

## Log Root

Default locations (in order of precedence):
1. `VNALPHA_LOG_ROOT` environment variable (if set)
2. `/var/log/openstock` (if writable — packaged/deployed mode)
3. `~/.local/state/openstock/logs` (local development fallback)

## Run Directory Layout

```
logs/
  runs/
    run_<run-id>/      # one directory per invocation
      audit.jsonl
      commands.jsonl
      errors.jsonl
      traces.jsonl
      app.jsonl
      repair.jsonl       # repair events only
      deploy.jsonl       # deploy events only
      ai-agent-summary.md
      environment.json
      README.md
    latest             # symlink or latest.txt pointing to newest run
  bundles/
    repair_NNN/        # repair bundles (ai-coding-prompt, manifest, etc.)
  deployments/
    <deployment-id>.json  # deploy state files
```

## Retention Guidelines

| Directory | Suggested Retention |
|-----------|---------------------|
| `runs/` | 30–90 days; delete oldest runs when disk usage grows |
| `bundles/` | Keep until the repair is confirmed resolved or archived |
| `deployments/` | Keep for the lifetime of the deployed version + one rollback window |

## Cleanup Commands

No automated cleanup commands exist yet. To manually prune old runs:

```bash
# List runs older than 30 days
find ~/.local/state/openstock/logs/runs -maxdepth 1 -type d -mtime +30

# Remove them (review first)
find ~/.local/state/openstock/logs/runs -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

## Disk Usage

A typical run produces < 1 MB of JSONL. A repair bundle adds ~50–200 KB.
Disk usage only becomes significant if thousands of runs accumulate.

## Symlink / latest.txt

The `runs/latest` symlink (or `runs/latest.txt`) always points to the most
recently created run directory. It is updated on each new run and used by
`vnalpha logs bundle --latest`, `vnalpha repair prepare --latest`, etc.

## No Secrets in Logs

Safe-mode redaction (default) and bundle exclusion rules ensure `.env`, `.pem`,
`.key`, and `secrets*` files are never copied into bundles. Still, treat the
`runs/` directory as potentially sensitive if content mode `full` was ever used.
