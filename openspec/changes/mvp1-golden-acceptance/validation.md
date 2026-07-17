# Validation Ledger

## Sanitized installed-host golden run (2026-07-17)

The exact implementation is the PR head containing this ledger. A fresh local
warehouse was provisioned through the real vnstock HTTP service and the real
assistant gateway; output prose and licensed values were deliberately not
retained.

| Check | Result |
|---|---|
| VCI symbol reference | passed; 1,745 STOCK symbols with exchange persisted |
| FiinQuantX FPT and VNINDEX provisioning | passed; 174 bounded rows per symbol were inserted as `RAW_UNADJUSTED` |
| Canonical/features/scoring | passed; 348 canonical rows, one FPT feature and one persisted watchlist score built |
| Natural-language turn 1 | passed; groundedness/policy `PASS`, correlated audit, artifacts and caveats present |
| Follow-up natural-language turn | passed; raw-row and ingestion-run counts did not change |
| Shared slash path | passed; `/analyze FPT` reused the same ready state |
| Validated memory | passed; exactly one active composite-score claim remained linked to validated evidence |
| Failure/degraded path | passed; typed LLM preflight failure did not disable deterministic analysis |
| Restart | passed; persisted state and provider probes survived service restart |

Required exact-head CI and merge evidence remain PR checks rather than being
inferred from this local run.
