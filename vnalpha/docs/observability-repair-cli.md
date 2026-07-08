# Repair CLI Reference

The `vnalpha repair` command group manages the closed-loop AI repair workflow. It packages failed run artifacts into a structured bundle that AI coding agents can consume, then tracks the repair lifecycle through fix, validation, and outcome recording.

## Commands

### `repair prepare`

Creates a repair bundle from a failed run.

```bash
vnalpha repair prepare --latest
vnalpha repair prepare --run-id <run-id>
```

**Options:**

| Flag | Description |
|------|-------------|
| `--latest` | Use the most recent run directory |
| `--run-id TEXT` | Use a specific run ID |
| `--bundles-root PATH` | Override default bundles root (default: `<log_root>/bundles`) |
| `--test-cmd TEXT` | Additional test command to embed in the bundle (repeatable) |
| `--mode [metadata\|redacted\|full]` | Content mode (default: redacted) |

**What it does:**

1. Locates the run directory under `~/.vnalpha/logs/runs/<run-id>/`
2. Creates `~/.vnalpha/logs/bundles/repair_NNN/` with:
   - `ai-coding-prompt.md` — structured prompt for AI coding agents
   - `reproduction.md` — how to reproduce the failure
   - `manifest.json` — metadata: error count, failed commands, top errors, suspicious patterns, test commands
   - `ai-agent-summary.md` — human-readable summary
   - `environment.json` — Python version, platform, dependencies
   - `raw-logs/` — safe copies of JSONL event files (secrets excluded)
3. Logs `REPAIR_PREPARED` event to `audit.jsonl` and `repair.jsonl`

**Example:**

```bash
vnalpha repair prepare --latest
# Created repair bundle: /home/user/.vnalpha/logs/bundles/repair_001
```

---

### `repair status`

Shows the current state of a repair bundle.

```bash
vnalpha repair status <repair-id>
vnalpha repair status <repair-id> --json
```

**Output includes:** bundle path, manifest summary, repair-state.json contents (started_at, fix_branch, pr_number, commit_sha, outcome, validation_passed).

---

### `repair start`

Records that an AI agent has started working on the repair.

```bash
vnalpha repair start <repair-id>
vnalpha repair start <repair-id> --agent "KiloCode"
```

Logs `REPAIR_STARTED` event. Updates `repair-state.json` with `started_at` and `agent`.

---

### `repair update`

Records fix metadata as the repair progresses.

```bash
vnalpha repair update <repair-id> \
  --fix-branch feat/fix-ohlcv-parse \
  --pr-number 47 \
  --commit-sha abc1234 \
  --outcome accepted
```

**Options:**

| Flag | Description |
|------|-------------|
| `--fix-branch TEXT` | Git branch name for the fix |
| `--pr-number TEXT` | Pull request number or URL |
| `--commit-sha TEXT` | Commit SHA of the fix |
| `--outcome [accepted\|rejected\|deferred]` | Final outcome of the repair |

Logs `REPAIR_UPDATED` event. Updates `repair-state.json`.

---

### `repair validate`

Runs the embedded test commands to validate the fix.

```bash
vnalpha repair validate <repair-id>
```

**What it does:**

1. Reads `test_commands` from `manifest.json`
2. Runs each command, captures exit code and output
3. Updates `repair-state.json` with `validation_passed`, `validation_at`, command results
4. Logs `REPAIR_VALIDATED` event to `audit.jsonl` and `repair.jsonl`

**Exit codes:** 0 if all commands pass, 1 if any fail.

---

## Repair Bundle Layout

```
~/.vnalpha/logs/bundles/
└── repair_001/
    ├── ai-coding-prompt.md      # Structured prompt for AI agents
    ├── reproduction.md          # Step-by-step reproduction guide
    ├── manifest.json            # Machine-readable metadata
    ├── ai-agent-summary.md      # Human-readable summary
    ├── environment.json         # Python/platform/deps snapshot
    ├── repair-state.json        # Mutable repair lifecycle state
    └── raw-logs/
        ├── commands.jsonl       # Command lifecycle events
        ├── errors.jsonl         # Captured exceptions
        ├── audit.jsonl          # Audit trail
        └── trace.jsonl          # Tool call traces
```

### `manifest.json` Fields

```json
{
  "bundle_id": "repair_001",
  "source_run_ids": ["20260708T143022"],
  "source_commit_sha": "abc1234",
  "redaction_mode": "redacted",
  "included_files": ["commands.jsonl", "errors.jsonl"],
  "error_count": 3,
  "failed_command_count": 1,
  "top_errors": ["KeyError: 'close'", "ValueError: ..."],
  "suspicious_patterns": ["COMMAND_FAILED"],
  "likely_modules": ["vnalpha.data.ohlcv"],
  "test_commands": ["cd vnalpha && make test-vnalpha"],
  "guardrails": "No broker/order/account/holdings/trading execution features. Data/analysis/observability scope only."
}
```

### `repair-state.json` Fields

```json
{
  "status": "validated",
  "started_at": "2026-07-08T14:45:00Z",
  "agent": "KiloCode",
  "fix_branch": "feat/fix-ohlcv-parse",
  "pr_number": "47",
  "commit_sha": "abc1234",
  "outcome": "accepted",
  "validation_passed": true,
  "validation_at": "2026-07-08T15:30:00Z"
}
```

---

## AI Coding Prompt Contract

The `ai-coding-prompt.md` file is the primary interface between VnAlpha's observability system and AI coding agents (KiloCode, Codex, Sisyphus).

### Required Sections

Every `ai-coding-prompt.md` contains:

1. **Guardrails** — hard constraints the AI must respect:
   ```
   GUARDRAILS: No broker/order/account/holdings/trading execution features.
   Data/analysis/observability scope only.
   ```

2. **Context** — run ID, commit SHA, error count, failed commands

3. **Top Errors** — list of exception types and messages from `errors.jsonl`

4. **Suspicious Patterns** — event types that indicate failure (COMMAND_FAILED, etc.)

5. **Likely Modules** — Python modules referenced in stack traces

6. **Required Test Commands** — commands the fix MUST pass before the repair is accepted:
   ```bash
   cd vnalpha && make test-vnalpha
   cd vnalpha && make lint-vnalpha
   ```

7. **Raw Log Reference** — path to `raw-logs/` for deeper inspection

### Guardrails Enforcement

The guardrails string appears in both `manifest.json` and `ai-coding-prompt.md`. AI agents must:

- Never introduce broker, order, account, holdings/portfolio, or trading execution features
- Stay within data ingestion, analysis, and observability scope
- Use `vnalpha repair update --outcome accepted/rejected/deferred` to record the outcome
