# 06. AI layer

> **Status:** current architecture and safety contract.
>
> Model aliases, production routing and delivery priority are owned by the linked
> GitHub issues. This document describes how AI participates in the implemented
> terminal-first workspace.

## Purpose

The AI layer converts validated research evidence into classification, bounded
plans, explanations, critiques and summaries. It is not the source of truth for
market data, readiness, scores, outcomes or research-policy decisions.

```text
deterministic warehouse/tool evidence
→ intent classification
→ bounded plan
→ allowlisted tool execution
→ strict structured synthesis
→ cited, caveated answer
```

## Current components

### Intent classifier

The classifier maps a user request to a typed intent and entities using a strict
JSON Schema contract. Invalid model output is rejected or repaired through an
explicit bounded retry; free-form text is not silently treated as a valid plan.

### Planner and policy checks

The planner produces typed requirements and tool steps. Before execution, policy
checks enforce:

- read-only research scope;
- allowlisted tools and parameters;
- required dates, symbols and context;
- data-readiness prerequisites;
- no raw SQL, shell or unrestricted network access.

### Deterministic tool execution

Tools delegate to shared application services used by CLI and TUI. AI cannot
bypass feature-completeness, canonical-data, benchmark, persistence or safety
contracts.

### Synthesizer

The synthesizer receives structured tool results and emits a strict response
schema containing the answer, basis, caveats, missing data and grounded source
references. It must not create a factual claim that cannot be mapped to provided
evidence.

### Gateway and model routing

`LLMGatewayClient` calls an OpenAI-compatible endpoint. Routing supports logical
profiles such as `small`, `default`, `reasoning` and `long_context`, but a profile
is only a real fallback when it resolves to a distinct verified model ID.

Configuration is fail-closed:

```bash
VNALPHA_LLM_ENDPOINT=
VNALPHA_LLM_MODEL=
VNALPHA_LLM_API_KEY=
```

The assistant remains unavailable until an explicit endpoint, dedicated
`VNALPHA_LLM_API_KEY`, and verified model alias are configured. The runtime does
not use `OPENAI_API_KEY` as an implicit fallback and ships no public endpoint or
guessed model ID. Deterministic CLI/TUI research functions continue to work.

Strict `json_schema` is preferred. Model capabilities are declared explicitly
per logical profile through `VNALPHA_MODEL_CAPABILITIES_<PROFILE>`; the runtime
does not infer support from a provider or model name. The primary route remains
callable for compatibility, but after a primary failure a strict request may
fall back only to a distinct profile that explicitly declares `json_schema`.
Unverified fallbacks are skipped. If no compatible fallback exists, the gateway
raises `LLMNoCompatibleFallbackError` with error code
`no_compatible_fallback` and preserves the primary failure as its cause.

A single compatibility downgrade from `json_schema` to `json_object` is allowed
per attempted model route only when the endpoint explicitly reports schema
support as unavailable. The downgrade does not create extra transport retry
budget. `/model status`, `/model profiles`, and `/model explain-route` expose
configured capabilities plus effective strict-schema fallbacks.

## Allowed uses

AI may:

- classify research requests;
- explain why deterministic rules produced a result;
- compare current evidence with stored historical outcomes;
- identify caveats and missing context;
- critique methodology or setup risk;
- summarize market, sector, symbol and data-readiness evidence;
- help prepare bounded research notes.

## Prohibited uses

AI must not:

- invent prices, fundamentals, sources or outcome statistics;
- call provider-specific SDKs or unrestricted web/data sources;
- execute arbitrary SQL or shell code;
- modify scoring, quality, routing or safety policy;
- treat memory, documents or prior model prose as authoritative evidence;
- present an event study or fixed-horizon proxy as a complete backtest;
- place or prepare broker/account/order/execution operations;
- claim certainty or provide guaranteed-performance language.

## Grounding and citations

Every substantive answer should preserve:

- requested and effective as-of date;
- tool and artifact identifiers;
- provider, ingestion and builder lineage where relevant;
- methodology and rule versions;
- missing required or optional evidence;
- caveats caused by stale, partial, legacy or unverified inputs.

Stored symbol memory is a retrieval aid, not an authority. Claims must be checked
against current structured evidence before they are used.

## Observability

The current warehouse records assistant and model activity through typed session
and trace tables. Safe observability includes:

```text
assistant session and stage
selected/effective model route
structured-output mode and downgrade status
latency and token usage
bounded prompt/output summaries
source/tool references
failure type and retry count
```

Raw prompts or responses are disabled by default and may be stored only through
an explicit reviewed configuration. Credentials and provider session material
must never enter traces.

## Interface behavior

The Textual TUI and Typer commands use the same assistant services. There is no
separate Streamlit AI implementation. A future read-only API may expose the same
service contract, but it must not duplicate prompt, policy, tool or routing
logic.

## Evaluation

AI changes require offline fixtures and runtime-replay evidence for:

- intent accuracy and clarification behavior;
- strict structured-output handling;
- tool selection and parameter safety;
- grounding and claim-to-source mapping;
- missing-data disclosure;
- model-route truthfulness;
- refusal of prohibited operations.

Evaluation output is evidence about assistant behavior; it does not replace
warehouse or domain-level correctness tests.
