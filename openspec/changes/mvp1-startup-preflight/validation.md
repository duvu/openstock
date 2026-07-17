# Validation Ledger

## Installed localhost acceptance (2026-07-17)

The exact implementation is the PR head containing this ledger. The vnstock
service was built locally, published only on `127.0.0.1:6900`, and exercised
with isolated XDG configuration and warehouse roots.

| Check | Result |
|---|---|
| Service health and readiness | passed before and after restart |
| Warehouse migration and clean initialization | passed in a fresh isolated warehouse |
| VCI reference synchronization | passed; 1,745 STOCK symbols with exchange and zero sync errors |
| Assistant preflight via local ya-router | passed through `127.0.0.1:7071` |
| Deterministic CLI/startup paths | passed, including `/analyze FPT` during LLM degradation |
| Restart durability | passed; raw, feature, score, audit and validated-memory state remained available |
| Package/startup verifier | passed in the candidate validation suite; exact-head CI remains required |

No source checkout was mounted into the service container and no secret or raw
licensed row was captured in this ledger.
