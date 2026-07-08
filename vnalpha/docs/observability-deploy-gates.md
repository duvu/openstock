# Deploy Promotion and Rollback Gates

## Overview

vnalpha enforces gates before any deployment promotion. No promotion can happen
without a passed verification run. This prevents deploying broken code and
ensures a rollback path is always recorded.

## Deploy Flow

```
vnalpha deploy verify <candidate-version>
  → DEPLOY_VERIFY_STARTED event
  → Runs: make test-vnalpha, make lint-vnalpha (or custom commands)
  → DEPLOY_VERIFY_COMPLETED event (status: PASSED or FAILED)
  → Saves state to deployments/<deployment-id>.json

vnalpha deploy promote <candidate> --deployment-id <id> --previous <prev>
  → Checks verification_status == PASSED (raises DeployGateError if not)
  → DEPLOY_PROMOTED event (logs candidate_version + previous_version)
  → Updates deployment state: deploy_status = PROMOTED

vnalpha deploy smoke <deployment-id> --passed   # or --failed
  → DEPLOY_SMOKE_COMPLETED event
  → Updates deployment state: smoke_status = PASSED/FAILED

vnalpha deploy rollback <deployment-id> --reason "smoke failed"
  → DEPLOY_ROLLBACK_STARTED event
  → DEPLOY_ROLLED_BACK event
  → Updates deployment state: rollback_status = ROLLED_BACK
```

## Verification Gate

`promote_candidate()` always checks `verification_status`:
- If `verification_status == "PASSED"` → promotion proceeds
- If `verification_status != "PASSED"` and `force=False` → raises `DeployGateError`
- A `DEPLOY_PROMOTION_BLOCKED` event is written when the gate fires

Using `--force` overrides the gate (not recommended, logged as `forced=true`).

## Deploy State File

State is stored at `deployments/<deployment-id>.json`:

```json
{
  "deployment_id": "deploy_20240101T120000_abc12345",
  "candidate_version": "v1.2.3",
  "previous_version": "v1.2.2",
  "verification_status": "PASSED",
  "deploy_status": "PROMOTED",
  "rollback_status": "NOT_REQUIRED",
  "smoke_status": "PASSED",
  "created_at": "2024-01-01T12:00:00+00:00",
  "promoted_at": "2024-01-01T12:05:00+00:00",
  "updated_at": "2024-01-01T12:10:00+00:00"
}
```

## Deploy Event Sequence in deploy.jsonl

```jsonl
{"event_type": "DEPLOY_VERIFY_STARTED",   "deployment_id": "...", "metadata": {"candidate_version": "v1.2.3"}, ...}
{"event_type": "DEPLOY_VERIFY_COMPLETED", "deployment_id": "...", "status": "PASSED", ...}
{"event_type": "DEPLOY_PROMOTED",         "deployment_id": "...", "metadata": {"candidate_version": "v1.2.3", "previous_version": "v1.2.2"}, ...}
{"event_type": "DEPLOY_SMOKE_COMPLETED",  "deployment_id": "...", "status": "PASSED", ...}
```

## Rollback Availability

The `previous_version` field is always logged in `DEPLOY_PROMOTED`. This means:
- You can always see what version to roll back to
- `vnalpha deploy rollback <deployment-id>` records the rollback event

## Custom Verification Commands

```bash
vnalpha deploy verify v1.2.3 \
  --command "cd vnalpha && make test-vnalpha" \
  --command "cd vnalpha && make lint-vnalpha"
```

Defaults (when no `--command` is given):
- `cd vnalpha && make test-vnalpha`
- `cd vnalpha && make lint-vnalpha`

## CLI Reference

```bash
vnalpha deploy verify <candidate>
vnalpha deploy verify <candidate> --deployment-id <id> --command "pytest"
vnalpha deploy promote <candidate> --deployment-id <id> --previous <prev>
vnalpha deploy promote <candidate> --deployment-id <id> --force    # override gate
vnalpha deploy rollback <deployment-id> --reason "smoke failed"
vnalpha deploy smoke <deployment-id> --passed
vnalpha deploy smoke <deployment-id> --failed --details "health check returned 500"
vnalpha deploy status <deployment-id>
vnalpha deploy list
```
