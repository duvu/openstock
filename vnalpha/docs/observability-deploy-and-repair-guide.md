# Deploy Gates & Promote/Rollback Reference

## Overview

The deploy gate prevents promoting unverified builds to production. Every promotion requires a prior `verify` step to pass. If verification fails, `promote` is blocked and logs a `DEPLOY_PROMOTION_BLOCKED` event.

## Workflow

```
vnalpha deploy verify <candidate>
  └─ Runs verify_commands (make test-vnalpha, make lint-vnalpha)
  └─ Saves state to: ~/.vnalpha/logs/deployments/<deployment-id>.json
  └─ Logs: DEPLOY_VERIFY_STARTED, DEPLOY_VERIFY_COMPLETED

vnalpha deploy promote <candidate> --deployment-id <id> --previous <previous-version>
  └─ Checks verification_status == "PASSED"
  └─ If FAILED → logs DEPLOY_PROMOTION_BLOCKED → raises DeployGateError → exits 1
  └─ If PASSED → logs DEPLOY_PROMOTED → returns result
  └─ Use --force to bypass gate (emergency only — logged as forced)

vnalpha deploy smoke <deployment-id> --passed / --failed
  └─ Logs DEPLOY_SMOKE_COMPLETED with smoke_passed field

vnalpha deploy rollback <deployment-id> [--reason "..."]
  └─ Logs DEPLOY_ROLLBACK_STARTED, DEPLOY_ROLLED_BACK
  └─ Updates deployment state with rollback_status, rollback_at, rollback_reason
```

## Commands

### `deploy verify`

```bash
vnalpha deploy verify <candidate> [--deployment-id TEXT] [--cmd TEXT]...
```

**Options:**

| Flag | Description |
|------|-------------|
| `--deployment-id TEXT` | Explicit deployment ID (auto-generated UUID4 if omitted) |
| `--cmd TEXT` | Override verify commands (repeatable). Default: `make test-vnalpha`, `make lint-vnalpha` |
| `--log-root PATH` | Override log root |

**Events logged:**

- `DEPLOY_VERIFY_STARTED` — before commands run
- `DEPLOY_VERIFY_COMPLETED` — after commands finish (includes `verification_status`: PASSED or FAILED)

**State saved:** `~/.vnalpha/logs/deployments/<deployment-id>.json`

---

### `deploy promote`

```bash
vnalpha deploy promote <candidate> \
  --deployment-id <id> \
  --previous <previous-version> \
  [--force]
```

**Gate:** Reads `verification_status` from the deployment state file. If not PASSED and `--force` is absent, exits with code 1 and logs `DEPLOY_PROMOTION_BLOCKED`.

**Events logged:**

- `DEPLOY_PROMOTION_BLOCKED` — when gate blocks promotion
- `DEPLOY_PROMOTED` — on success, includes `candidate_version`, `previous_version`

---

### `deploy smoke`

```bash
vnalpha deploy smoke <deployment-id> --passed
vnalpha deploy smoke <deployment-id> --failed
```

Records post-deployment smoke test result.

**Events logged:** `DEPLOY_SMOKE_COMPLETED` with `smoke_passed: true/false`

---

### `deploy rollback`

```bash
vnalpha deploy rollback <deployment-id> [--reason "reason text"]
```

**Events logged:**

- `DEPLOY_ROLLBACK_STARTED`
- `DEPLOY_ROLLED_BACK` (includes `rollback_reason`, `rollback_at`)

**State updated:** `rollback_status`, `rollback_at`, `rollback_reason` written to deployment state.

---

### `deploy status`

```bash
vnalpha deploy status <deployment-id>
```

Shows deployment state JSON.

---

### `deploy list`

```bash
vnalpha deploy list
```

Lists all deployment IDs under the log root.

---

## Deployment State File

Location: `~/.vnalpha/logs/deployments/<deployment-id>.json`

```json
{
  "deployment_id": "d1234abcd",
  "candidate_version": "0.4.2",
  "previous_version": "0.4.1",
  "verification_status": "PASSED",
  "verify_results": [
    {"command": "cd vnalpha && make test-vnalpha", "passed": true, "exit_code": 0},
    {"command": "cd vnalpha && make lint-vnalpha", "passed": true, "exit_code": 0}
  ],
  "verified_at": "2026-07-08T14:00:00Z",
  "promoted_at": "2026-07-08T14:10:00Z",
  "smoke_passed": true,
  "rollback_status": null,
  "rollback_reason": null,
  "rollback_at": null
}
```

---

## Rollback Assumptions

- **Rollback is idempotent**: calling `rollback` on an already-rolled-back deployment logs a new event but does not error.
- **Rollback is advisory**: the CLI records the intent and events; actual version reversion is the operator's responsibility (git revert, Docker tag swap, etc.).
- **No automatic rollback on smoke failure**: smoke failure logs an event but does not automatically trigger rollback. The operator must explicitly call `deploy rollback`.
- **Force promotion is audited**: `--force` is logged as a forced promotion in `DEPLOY_PROMOTED` event fields. Force bypasses the gate but leaves a full audit trail.
- **Partial verification**: if verify commands are partially overridden via `--cmd`, the deployment state reflects only the supplied commands. Default commands cover tests + lint.

---

## Manual vs AI-Assisted vs Automatic Steps

| Step | Trigger | Who acts |
|------|---------|----------|
| `repair prepare` | Failed run detected | Operator or cron job |
| Bundle delivery to AI | Manual hand-off | Operator |
| `repair start` | AI agent begins | AI agent or operator |
| Code fix | Coding session | AI agent (KiloCode/Codex/Sisyphus) |
| `repair update --fix-branch` | PR opened | AI agent or CI |
| `repair validate` | Tests pass/fail | CI or operator |
| `repair update --outcome` | Fix accepted/rejected | Operator |
| `deploy verify` | After merge | CI pipeline |
| `deploy promote` | After verify passes | Operator or CI |
| `deploy smoke` | Post-deploy check | Monitoring or operator |
| `deploy rollback` | Smoke fails or issue detected | Operator |

**Fully automatic** (no human needed): `repair prepare`, `repair validate`, `deploy verify`, `deploy smoke` recording.

**Human-gated**: `repair update --outcome`, `deploy promote` (unless CI is trusted to auto-promote after gate passes).

**AI-assisted**: code fix, PR creation, commit.

---

## Handing Bundles to AI Coding Agents

### KiloCode / Codex

1. Run `vnalpha repair prepare --latest`
2. Note the bundle path printed to stdout
3. Open `<bundle>/ai-coding-prompt.md` and paste its contents as the initial prompt to the AI agent
4. Or reference the raw logs: `<bundle>/raw-logs/*.jsonl`
5. After the fix: `vnalpha repair update <repair-id> --fix-branch <branch> --commit-sha <sha>`
6. After CI runs: `vnalpha repair validate <repair-id>`
7. Record outcome: `vnalpha repair update <repair-id> --outcome accepted`

### Sisyphus (OpenCode)

Sisyphus can be invoked with the bundle path directly. The `ai-coding-prompt.md` follows the structured format that Sisyphus's task system understands. Key fields:

- **Guardrails** — Sisyphus respects the no-trading-execution constraint
- **Required Test Commands** — Sisyphus will run these before declaring the fix complete
- **Suspicious Patterns** — helps Sisyphus narrow root cause investigation

### Automated CI Integration

```yaml
# Example GitHub Actions step
- name: Prepare repair bundle on failure
  if: failure()
  run: vnalpha repair prepare --latest --mode redacted
```

The bundle is then attached as a CI artifact for manual or automated AI review.
