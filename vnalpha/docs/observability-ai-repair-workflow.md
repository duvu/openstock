# Closed-Loop AI Repair Workflow

## Overview

When a vnalpha run fails, the observability system generates a structured repair
bundle that an AI coding agent can consume to diagnose, fix, and validate the issue —
without human intervention at every step.

## Full Scenario

```
Runtime failure
  → run directory: errors.jsonl, commands.jsonl, audit.jsonl
  → vnalpha repair prepare --latest
  → bundles/repair_NNN/
      ai-coding-prompt.md     ← what to fix and how to test
      reproduction.md         ← exact failing commands
      manifest.json           ← metadata, guardrails
      raw-logs/               ← safe JSONL copies
  → AI agent reads ai-coding-prompt.md
  → vnalpha repair start <repair-id> --agent <agent-name>
  → AI agent creates fix branch, opens PR
  → vnalpha repair update <repair-id> --fix-branch fix/foo --pr-number 42
  → AI agent or CI runs: vnalpha repair validate <repair-id>
  → (if PASSED) vnalpha repair update <repair-id> --outcome accepted
  → Deploy: vnalpha deploy verify <candidate-version>
  → (if PASSED) vnalpha deploy promote <candidate> --deployment-id <id>
  → Post-deploy: vnalpha deploy smoke <deployment-id> --passed
```

## What is Automatic vs. Human-Gated

| Step | Who does it | Gate |
|------|-------------|------|
| Run failure captured | Automatic — instrumentation | — |
| Repair bundle created | Human or CI triggers `vnalpha repair prepare` | Human/CI trigger |
| AI agent reads bundle | Automatic — agent consumes `ai-coding-prompt.md` | — |
| Fix branch + PR | AI agent creates branch/PR | AI-assisted |
| Validation (`repair validate`) | CI or AI agent runs it | Must PASS |
| Deploy verify | CI or human triggers `vnalpha deploy verify` | Must PASS |
| Deploy promote | Human decision or CI with guard | Must verify first |
| Post-deploy smoke | Automatic or human | Records result |

## Guardrails Enforced

Every `ai-coding-prompt.md` and `manifest.json` includes this guardrail:

> **DO NOT** add, modify, or enable any of:
> - Broker connectivity or order execution
> - Account, portfolio, or position management features
> - Trading signal execution or live-order routing
> - Any feature that interacts with live financial market APIs beyond read-only data

AI agents **cannot bypass** deploy verification or validation gates:
- `promote_candidate()` raises `DeployGateError` if `verification_status != PASSED`
- `repair validate` exits with code 1 if any test command fails
- Audit events record every attempt, including blocked promotions

## Repair Event Sequence in repair.jsonl

```jsonl
{"event_type": "REPAIR_PREPARED", "repair_id": "repair_001", ...}
{"event_type": "REPAIR_STARTED",  "repair_id": "repair_001", "metadata": {"agent": "..."}, ...}
{"event_type": "REPAIR_UPDATED",  "repair_id": "repair_001", "metadata": {"fix_branch": "fix/foo"}, ...}
{"event_type": "REPAIR_UPDATED",  "repair_id": "repair_001", "metadata": {"pr_number": "42"}, ...}
{"event_type": "REPAIR_VALIDATED","repair_id": "repair_001", "status": "PASSED", ...}
{"event_type": "REPAIR_UPDATED",  "repair_id": "repair_001", "metadata": {"outcome": "accepted"}, ...}
```

## CLI Commands

```bash
# Prepare repair bundle from latest failed run
vnalpha repair prepare --latest

# Start repair session (log AI agent start)
vnalpha repair start <repair-id> --agent claude

# Update tracking fields
vnalpha repair update <repair-id> --fix-branch fix/foo
vnalpha repair update <repair-id> --pr-number 42 --commit-sha abc1234

# Run validation commands from bundle
vnalpha repair validate <repair-id>

# Mark outcome
vnalpha repair update <repair-id> --outcome accepted

# Check status
vnalpha repair status <repair-id>
vnalpha repair status <repair-id> --json
```
