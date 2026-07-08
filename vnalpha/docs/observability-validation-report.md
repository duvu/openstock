# Observability Validation Report

## Purpose

This document records evidence that the file-based observability system meets its
functional requirements. Evidence comes from the test suite, CLI dry-runs, and
code review.

## Test Suite Results

All tests pass under `make test-vnalpha`.

Key test files:
- `tests/test_observability.py` — sections 1–12: context, JSONL, redaction, commands, errors, chat, tools, pipeline, summary, logs CLI
- `tests/test_observability_domain.py` — domain-level pipeline/feature/scoring event logging
- `tests/test_repair.py` — sections 13–14: repair bundle generation, unsafe file exclusion, repair event tracking
- `tests/test_deploy.py` — sections 15–16: deploy event generation, gate enforcement, end-to-end scenario

## Functional Requirements Verified

| Requirement | Test(s) | Status |
|------------|---------|--------|
| Repair bundle created under `bundles/<id>/` | `test_bundle_dir_created` | ✓ |
| `ai-coding-prompt.md` generated | `test_required_files_present` | ✓ |
| `manifest.json` has required fields | `test_manifest_required_fields` | ✓ |
| Guardrails in manifest + prompt | `test_manifest_has_guardrails`, `test_ai_coding_prompt_contains_guardrails` | ✓ |
| Unsafe files excluded from raw-logs | `test_secrets_env_excluded`, `test_pem_excluded` | ✓ |
| REPAIR_PREPARED event written | `test_repair_prepared_event_written` | ✓ |
| REPAIR_STARTED event written | `test_repair_started_event` | ✓ |
| Fix branch, PR, commit SHA logged | `test_repair_updated_fix_branch`, `*_pr_number`, `*_commit_sha` | ✓ |
| Validation results logged | `test_repair_validated_event` | ✓ |
| Outcome (accepted/rejected/deferred) logged | `test_repair_outcome_accepted` | ✓ |
| Repair events appear in audit.jsonl | `test_repair_event_also_written_to_audit` | ✓ |
| Deploy events written to deploy.jsonl | `test_verify_started_event_written`, etc. | ✓ |
| Deploy events appear in audit.jsonl | `test_deploy_event_also_in_audit` | ✓ |
| Previous + candidate version logged | `test_deploy_promoted_event` | ✓ |
| Promotion blocked when unverified | `test_promotion_blocked_when_unverified` | ✓ |
| Promotion succeeds when verified | `test_promotion_succeeds_when_verified` | ✓ |
| Rollback events written | `test_rollback_events` | ✓ |
| Rollback state persisted | `test_rollback_state_persisted` | ✓ |
| Full e2e scenario passes | `test_full_scenario_repair_to_deploy` | ✓ |
| `repair prepare` consumes failed run | `test_failed_run_generates_repair_bundle` | ✓ |

## CLI Commands Verified (Import Smoke)

```
vnalpha logs bundle --latest      ← logs_app registered
vnalpha repair prepare --latest   ← repair_app registered
vnalpha repair start <id>         ← REPAIR_STARTED event
vnalpha repair validate <id>      ← REPAIR_VALIDATED event
vnalpha repair status <id>        ← reads state
vnalpha repair update <id>        ← REPAIR_UPDATED event
vnalpha deploy verify <candidate> ← DEPLOY_VERIFY_* events
vnalpha deploy promote <candidate>← gate enforced
vnalpha deploy rollback <id>      ← DEPLOY_ROLLBACK_* events
vnalpha deploy smoke <id>         ← DEPLOY_SMOKE_COMPLETED event
vnalpha deploy status <id>        ← reads state
vnalpha deploy list               ← lists deployments
```

## Redaction Verified

- Default mode is `redacted`
- Sensitive key names are replaced with `"<redacted>"`
- Full mode requires explicit opt-in (`VNALPHA_LOG_MODE=full`)
- Unsafe files excluded from bundles (`*.pem`, `*.env`, `secrets*`, `*.key`)

## Known Deferred Items

| Task | Reason |
|------|--------|
| 9.6 Restore logging | No restore script exists yet; deferred until added |
| 0.6 AI repair bypass governance | Enforced in code (`DeployGateError`); formal policy doc deferred |

## Validation Date

Generated: 2026-07-08
