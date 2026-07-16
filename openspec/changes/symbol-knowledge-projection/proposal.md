## Why

OpenStock already has a mature symbol-memory subsystem — typed claims, an
append-only event log, claim lifecycle (accept/supersede/expire/conflict),
Markdown knowledge cards, retrieval, correction, compaction and a
source-grounding gate that rejects anything not backed by a persisted
warehouse artifact. Candidate scoring already projects its score into memory.

But after a successful chat deep-analysis turn, the other deterministic
evidence the turn produced — the feature-quality snapshot, the candidate
score/class/setup-type, and (when requested) the current market-regime context —
is not projected. Users get an answer, yet the per-symbol knowledge base does
not accumulate the same deterministic evidence for later questions.

Issue #164 closes that gap: after a successful MVP1 analysis, project the
approved deterministic evidence into the symbol knowledge base idempotently,
with provenance and lifecycle controls, never promoting raw chat text or LLM
prose as factual claims.

## What Changes

- add one post-analysis evidence projector,
  `project_analysis_evidence`, invoked from `AssistantApp.execute_prepared`
  only after synthesis succeeds and both groundedness and research policy pass
  (the same gate `_persist_research_audit` already enforces), and only for
  deep-analysis intents;
- the projector reads the persisted, grounded artifacts the turn produced
  (candidate score, feature snapshot, market-regime snapshot when a snapshot is
  present) and projects each through the existing `symbol_memory` adapters +
  `SymbolMemoryIngestionService`, wrapped in
  `SymbolMemoryCompactionService.mutate_and_compact` — mirroring the existing
  `generate_watchlist._project_candidate_score_to_memory` path so the knowledge
  card is compacted after projection;
- reuse the existing idempotency, supersession, lifecycle, provenance and
  `has_persisted_evidence` source-grounding guards unchanged; the projector adds
  no second knowledge store and cannot inject un-persisted evidence;
- projection is best-effort and fail-open for the answer: a projection failure
  is logged and surfaced as a caveat but never fails an already-valid answer,
  and a failed/partial/policy-rejected analysis projects nothing;
- surface what was learned/updated in the answer's research metadata trace.

## Capabilities

### Added Capabilities

- `symbol-knowledge-projection`: automatic, idempotent, provenance-tracked
  projection of validated deterministic analysis evidence into the per-symbol
  knowledge base after a successful chat analysis.

## Impact

- `vnalpha/src/vnalpha/symbol_memory/` (new `projection.py`), `assistant/app.py`;
- reuses `symbol_memory/adapters.py`, `ingestion.py`, `compaction.py`,
  `repository.py`, `research_models/repositories.py`,
  `warehouse/repositories.py`;
- tests in `vnalpha/tests/test_issue_164_evidence_projection.py`;
- No change to the read-only research boundary. Memory cannot change policy,
  tools or approvals. No raw conversation or model prose becomes a factual claim.
