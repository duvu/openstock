# Issue #255: Operational Proof Requirements

## Objective
Demonstrate 10 consecutive live daily-maintenance sessions on a supported host.

## Prerequisites
- Issues #252, #253, #254 must be complete and merged
- Maintenance ledger operational
- Calendar validity enforced
- Dataset readiness queries functional

## Procedure

### 1. Enable Daily Maintenance Timer
```bash
# Configure systemd timer or cron
vnalpha maintain daily --date today
```

### 2. Evidence Collection Per Session
For each of 10 consecutive Vietnamese market sessions, collect:

- Run ID and correlation ID
- Requested/effective date
- Symbol counts (requested/successful/failed)
- Provider and dataset readiness snapshot
- Rows inserted/upserted, gaps (true/repaired)
- Features, scores, market/group snapshots
- Memory claims (created/superseded/expired/rejected/conflicted)
- Duration, status, diagnostics references

### 3. Query Ledger
```bash
# Latest run
vnalpha maintain status

# JSON export
vnalpha maintain status --json > evidence/run-<date>.json
```

### 4. Manual Rerun Evidence
For at least 2 sessions, demonstrate same-date rerun:
```bash
vnalpha maintain daily --date 2026-07-17  # First run
vnalpha maintain daily --date 2026-07-17  # Rerun (no duplicates)
```

### 5. Validation Criteria
- [x] 10 consecutive market sessions with persisted records
- [ ] Provider/symbol failures produce PARTIAL without losing successful symbols
- [ ] No flattened/unactionable generic failures
- [ ] Same-date reruns create separate invocation records
- [ ] One-writer lock prevents timer/manual overlap
- [ ] Incremental acquisition (not full reload every session)
- [ ] Current symbol analysis uses accumulated evidence
- [ ] Report separates live vs fixture evidence

## Evidence Submission
1. Export ledger for 10 sessions: `vnalpha maintain status --json`
2. Collect logs/diagnostics for any failures
3. Document environment (OS, Python, calendar version)
4. Attach to PR closing #255

## Notes
- Cannot be automated in unit tests - requires real system operation
- Partial failures are acceptable and demonstrate robustness
- Lock contention should be gracefully handled
