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

### 6. One-command proof aggregation

After the timer has run over the required sessions, aggregate the persisted
ledger into the proof report with a single command:

```bash
# Human-readable summary (exits non-zero until 10 sessions are recorded)
vnalpha maintain proof

# Machine-readable evidence to attach to the closing PR
vnalpha maintain proof --json > evidence/operational-proof.json
```

`maintain proof` reads the ledger truthfully: it collapses same-date reruns to
one distinct session (flagging the reran dates), surfaces the latest invocation
per date with status/symbol counts/source policy, and reports
`has_required_sessions`. It never fabricates live operation.

## Evidence Submission
1. Export the aggregated proof: `vnalpha maintain proof --json`
2. Collect logs/diagnostics for any failures
3. Document environment (OS, Python, calendar version)
4. Attach to PR closing #255

## Notes
- The 10 live consecutive sessions themselves cannot be produced or unit-tested:
  they require real trading days and live providers on a supported host. The
  operator owns running the timer; `maintain proof` makes assembling the
  evidence turnkey once the sessions exist.
- Partial failures are acceptable and demonstrate robustness
- Lock contention should be gracefully handled
