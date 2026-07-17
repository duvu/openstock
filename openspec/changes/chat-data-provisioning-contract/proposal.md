## Why

OpenStock had two incomplete provisioning behaviours. Analysis tools implicitly
called data-availability helpers before execution (off-trace, error-swallowing),
while explicit natural-language requests such as `tải/cập nhật dữ liệu FPT`
classified as `fetch_data` but the planner refused them and required a manual
command. Users could not rely on one consistent chat contract for
`request → provision → persist → analyze → answer`.

Issue #163 made bounded current-symbol data provisioning a first-class, visible
application step shared by natural-language chat and slash commands. Follow-on
issue #175 owns fail-closed legacy remediation parsing, while #162 owns the
integrated acceptance path.

## What Changes

- add one typed application operation `ensure_current_symbol_ready` in
  `vnalpha.data_provisioning` that delegates to the existing fail-closed
  `DeepAnalysisReadinessService` and the `data_availability` engine, returning a
  typed `CurrentSymbolReadyResult` with per-action status, correlation ID,
  reuse/refresh classification and remediation;
- add a bounded `force_refresh` path to the `data_availability` engine that
  performs bounded incremental provisioning even when data already looks fresh;
- expose the operation through a new assistant-eligible tool
  `data.ensure_current_symbol`, recorded on the tool/audit trace;
- replace the `fetch_data` planner refusal with a real provisioning step and
  prepend an explicit provisioning step to the deep-analysis plan, removing the
  hidden executor-only pre-step for those flows;
- fail closed: a failed or partial provisioning turn stops downstream analysis;
- route `/analyze` through the same operation so slash and natural language share
  one application contract;
- keep the unrestricted `data.fetch` tool command-only and non-autonomous.

## Capabilities

### Added Capabilities

- `chat-data-provisioning-contract`: one explicit, idempotent, correlation-traced
  current-symbol provisioning operation shared by chat and slash commands.

## Impact

- `vnalpha/src/vnalpha/data_provisioning/`, `data_availability/`,
  `tools/`, `policy/tool_policy.py`, `assistant/planner.py`,
  `assistant/executor.py`, `assistant/groundedness.py`,
  `commands/handlers/analyze.py`;
- documentation in `docs/data-provisioning-commands.md`;
- tests in `vnalpha/tests/test_issue_163_chat_provisioning.py` and updated
  planner/executor/groundedness/readiness regressions.
- No change to the read-only research boundary. No SQL, filesystem, shell,
  network, broker, account, order, portfolio or execution capability is added.
