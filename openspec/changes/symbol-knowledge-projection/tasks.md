# Tasks: symbol knowledge projection (issue #164)

- [x] 1. Add `symbol_memory/projection.py` with `project_analysis_evidence`
      reusing adapters + ingestion + compaction (best-effort, fail-open).
- [x] 2. Project candidate score and feature-quality snapshot from the
      deep-analysis tool outputs, read back from persisted rows for grounding.
- [x] 3. Hook the projector into `AssistantApp.execute_prepared` after synthesis
      succeeds and groundedness+policy pass, only for deep-analysis intents.
- [x] 4. Record projected claim summaries in the answer research metadata; record
      a caveat on projection failure without failing the answer.
- [x] 5. Add focused tests: first projection, repeat idempotency, supersession,
      un-persisted (prose) rejection, non-deep-analysis skip, next-turn retrieval
      and an end-to-end app projection.
- [ ] 6. Record final CI evidence on the merge SHA in `validation.md` (pending PR).
