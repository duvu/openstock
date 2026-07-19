## 1. Daily maintenance runtime

- [x] 1.1 Add typed daily request/result/stage contracts and one deterministic service sequence. [evidence: `vnalpha/src/vnalpha/maintenance/`, `vnalpha/tests/test_issue_239_daily_maintenance.py`]
- [x] 1.2 Reuse current canonical/source evidence, isolate failed symbols and preserve typed provider diagnostics. [evidence: `vnalpha/tests/test_issue_239_daily_maintenance.py`, `vnalpha/tests/test_issue_232_provider_diagnostics.py`]
- [x] 1.3 Add dry-run and explicit non-session mutation-free behavior. [evidence: `vnalpha/tests/test_issue_239_daily_maintenance.py`]
- [x] 1.4 Add and validate the versioned Vietnam exchange-holiday calendar used by the default service. [evidence: `vnalpha/src/vnalpha/ingestion/trading_calendar.py`, `vnalpha/tests/test_issue_239_daily_maintenance.py`]
- [x] 1.5 Complete CLI JSON/exit-code, empty scope, repeated-run and mutable-table idempotency tests. [evidence: `vnalpha/tests/test_issue_239_daily_maintenance.py`]

## 2. Knowledge-loop integration

- [x] 2.1 Run selective symbol projection after validated daily builders and report lifecycle counters. [evidence: `vnalpha/tests/test_issue_240_selective_symbol_memory.py`]
- [x] 2.2 Preserve existing symbol APIs while adding collision-safe typed entity identity and compaction. [evidence: `vnalpha/tests/test_issue_241_entity_memory.py`, `vnalpha/tests/test_symbol_memory_*.py`]
- [x] 2.3 Build deterministic point-in-time market, sector, industry and asset-class context and project only changed snapshots. [evidence: `vnalpha/tests/test_issue_242_group_context_memory.py`]
- [x] 2.4 Prove legacy memory-table migration without event, claim, document or compaction-history loss. [evidence: `vnalpha/tests/test_issue_241_entity_memory.py`]

## 3. Scheduling and package delivery

- [x] 3.1 Package the exact daily service/timer with explicit timezone, partial-success exit and stable `flock`. [evidence: `packaging/tests/test_daily_pipeline_units.sh`]
- [x] 3.2 Keep installation and upgrade disabled by default; reload units and stop only on removal. [evidence: `packaging/tests/test_daily_pipeline_units.sh`]
- [x] 3.3 Document enable, disable, manual run, inspection, JSON result and contention behavior. [evidence: `packaging/docs/OPERATOR.md`]
- [x] 3.4 Build the Debian artifact and verify unit payload, package identity and clean install behavior. [evidence: `packaging/build-deb.sh`, `packaging/test/test_packaging.sh`, Debian 12 clean-host install transcript]

## 4. Roadmap truth

- [x] 4.1 Point current root, component and OpenSpec documents to the exact #238 URL and reject #90/#209 drift. [evidence: `scripts/tests/test_check_repo_consistency.py`, `python scripts/check-repo-consistency.py`]
- [x] 4.2 Add the canonical product loop, three truth layers and historical-document banners. [evidence: `README.md`, `docs/ROADMAP.md`, `vnalpha/docs/01-vision-and-scope.md`]

## 5. Exact-candidate acceptance

- [x] 5.1 Run focused issue matrices plus complete vnalpha, vnstock, packaging, repository, OpenSpec and evaluation gates. [evidence: full `vnalpha` suite; 1,388 offline `vnstock` tests; 60 package checks; repository, OpenSpec and 5/5 fixture plus 22/22 runtime evaluations]
- [x] 5.2 Run the prepared clean-host install, preflight, data, maintenance, CLI/TUI/assistant, repeat and failure-injection transcript against the exact package and commit. [evidence: Debian 12/Python 3.11 clean-host transcript; 42 installed issue tests; 87 installed CLI/TUI/assistant/safety tests; timer and lock checks]
- [ ] 5.3 Publish a sanitized #245 acceptance report with exact identities, commands, outcomes and explicit fixture/live-provider limitations.

## 6. Lifecycle reconciliation

- [x] 6.1 Update overlapping active OpenSpec entries with #231–#244 evidence and validate every affected change strictly. [evidence: strict validation of `core-data-knowledge-loop`, `chat-data-provisioning-contract` and `symbol-knowledge-memory`]
- [ ] 6.2 Publish the exact candidate, wait for required GitHub checks, then close child issues in dependency order.
- [ ] 6.3 Close #238 only after #245 evidence is accepted; close backlog-gated #235 as not planned unless qualifying evidence exists.
