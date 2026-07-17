# Validation Ledger

## Local production-route acceptance (2026-07-17)

The exact implementation is the PR head containing this ledger. Local
ya-router was exercised through the deployed `thiendu` route at
`http://127.0.0.1:7071/v1/chat/completions`; no token, provider credential,
model prose or licensed data was recorded.

| Check | Result |
|---|---|
| Router health and refreshed catalog | passed; two authenticated providers were ready and `thiendu` selected a fresh routable model |
| `vnalpha preflight` structured-output probe | passed with exit 0 and route status `READY` |
| Real Vietnamese FPT natural-language request | passed with groundedness and policy `PASS`, two audited tools, three artifact references and correlation evidence |
| Unreachable route classification | passed; preflight returned typed `UNAVAILABLE` with exit 1 |
| Deterministic degraded operation | passed; `/analyze FPT` remained available while the LLM endpoint was unreachable |

Required exact-head CI and merge evidence remain owned by the PR checks and are
not inferred from this local smoke run.
