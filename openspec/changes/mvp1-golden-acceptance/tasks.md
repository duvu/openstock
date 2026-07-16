# Tasks: MVP1 golden acceptance (issue #167)

- [x] 1. Add the golden conversation test seeding raw OHLCV at the fetch boundary
      and running the real canonical/feature/scoring builders + real
      planner/executor/synthesis/groundedness/audit/projection.
- [x] 2. Assert turn 1: visible provisioning trace, persisted symbols/OHLCV/
      VNINDEX/features/real score, grounded audit with as-of/evidence/freshness/
      caveats, and projected knowledge whose value equals the persisted score.
- [x] 3. Assert turn 2 fresh reuse with zero new provider fetches and idempotent
      projection.
- [x] 4. Assert explicit refresh threads force-refresh and discloses bounded
      actions.
- [x] 5. Assert a service-unavailable failure fails closed and preserves state.
- [x] 6. Assert slash/NL share the same `ensure_current_symbol_ready` contract.
- [ ] 7. Record required-CI green on the final release SHA and the one sanitized
      installed-host smoke run in `validation.md` (pending PR / release SHA).
