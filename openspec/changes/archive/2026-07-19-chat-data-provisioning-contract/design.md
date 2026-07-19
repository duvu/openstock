## Context

Chat, slash commands, and legacy assistant paths previously reached current-symbol
data through different call chains. That made provisioning invisible in some
traces, allowed failures to lose their typed public contract, and coupled a
bounded data request to full deep-analysis readiness.

## Decisions

### One typed application boundary

`ensure_current_symbol_ready` is the shared application operation. Plans invoke
it through `data.ensure_current_symbol`; slash commands call the same operation.
The executor does not add a second hidden provisioning step when the plan already
contains one.

### Separate data-only and analysis-ready semantics

Deep analysis retains the complete readiness contract. Explicit `fetch_data`
uses the same bounded operation with `data_only=True`, which permits only the
symbol-scoped OHLCV and canonical stages and never constructs deep readiness.

### Resolve the target date once

The assistant resolves explicit classified date, request/default date, or the
Vietnam-market current date before planning. The resolved date is copied into
the request, tool arguments, persisted session state, and public output.

### Preserve typed failure provenance

The vnstock service emits bounded structured diagnostics. The client, ingestion,
warehouse, CLI, and TUI preserve safe status, code, retryability, provider, and
correlation fields without retaining raw response bodies. Only explicitly public
tool failures receive actionable public presentation; ordinary exceptions remain
generic and fail closed.

### Keep the research boundary narrow

The operation is limited to deterministic application services. It provides no
SQL, filesystem, shell, code execution, broker, order, account, portfolio, or
trading capability, and the assistant cannot autonomously invoke unrestricted
`data.fetch`.

## Compatibility and validation

Existing symbol-ready wrappers and legacy chat dispatch remain supported. The
contract is covered across immediate, approval, legacy, CLI, TUI, readiness,
package, and runtime-evaluation paths, with exact-candidate evidence recorded in
PR #247 and issues #231–#233.
