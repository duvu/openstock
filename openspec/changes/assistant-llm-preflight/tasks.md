# Tasks: assistant LLM preflight (issue #165)

- [x] 1. Add `assistant/preflight.py`: `LLMPreflightCode`, `LLMPreflightResult`,
      `run_llm_preflight` with an injectable bounded probe and typed classification.
- [x] 2. Classify config, credential, routing, transport, HTTP 401/403/404/5xx
      and structured-output-rejection outcomes; unwrap no-compatible-fallback to
      its real primary cause.
- [x] 3. Add the `vnalpha preflight` CLI command (human + `--json`), exiting
      non-zero when unavailable with a degraded-mode note.
- [x] 4. Surface the degraded-mode message in `vnalpha ask`; upgrade the
      `openstock-verify` assistant check to the typed preflight.
- [x] 5. Document the single verified-model MVP1 decision and the preflight in
      `.env.example` and `packaging/config/vnalpha.env`.
- [x] 6. Add focused tests using a fake gateway (no live network) covering every
      typed code, redaction safety and the CLI plumbing.
- [ ] 7. Record real redacted production smoke evidence + final CI on the merge
      SHA in `validation.md` (pending PR / deployed host).
