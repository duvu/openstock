## Decision

The request boundary retains the `today` sentinel only for an implicit
current-symbol intent. `DeepAnalysisReadinessService` then finds the latest
canonical target/VNINDEX date at or before the current market session that has
the required lookback. This selects evidence before feature and score
provisioning, rather than requiring a score to already exist.

Explicit ISO dates never enter this fallback path. The resolved readiness date
continues to drive artifact evidence, warnings, and remediation commands.
