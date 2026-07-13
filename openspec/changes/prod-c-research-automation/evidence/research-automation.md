# Research automation implementation evidence

Base commit: `873425d62eb1aea7fc7519b62fde22ac195c7872` plus the current working tree.

Implemented surfaces:

- `/feature create` and `/feature validate` with definition safety checks, metadata-first persistence, schema/coverage validation, lineage, and quality status.
- `/experiment indicator` using persisted 20-session relative strength versus VNINDEX.
- `/pattern scan` using bounded accumulation-base, volatility-contraction, and volume-dry-up thresholds.
- `/hypothesis test` with structured sample, condition, outcome, horizon, metric, assumptions, and plan preview.
- `/experiment backtest` rendered and persisted exclusively as an offline research event study.
- Six assistant intents, deterministic plan templates, policy-approved local tools, and packaged runtime replay cases.
- DuckDB artifact metadata plus canonical manifest, result, summary, lineage, validation, reproducibility, metrics, and candidate files.

Safety observations:

- Generated code is not used by these MVP workflows; computation runs through approved deterministic tools.
- Existing sandbox contracts remain the only generated-code execution path and require exact retained-plan approval.
- Future-data feature expressions and execution-oriented event-study requests are rejected.
- Insufficient persisted coverage creates a partial/rejected result instead of a success claim.
- Every artifact carries research-only caveats and no personalized recommendation text.

Validation summary:

- Full vnalpha test suite: PASS.
- Ruff lint and format: PASS.
- R4 acceptance suite: PASS.
- Installed wheel/package runtime corpus tests: PASS with 16 runtime cases.
- `openstock-verify --ci`: PASS with 16 OK, 1 environment warning, 0 failures.
- Focused research automation suite: PASS.
