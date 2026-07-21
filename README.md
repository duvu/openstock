# OpenStock

**OpenStock is an evidence-first, provider-independent research platform for Vietnamese equities.**

It combines a normalized market-data layer with a reproducible research workspace:

```text
vnstock  = provider plugins + canonical data contracts + quality + read-only service
vnalpha  = DuckDB research warehouse + analysis + watchlists + CLI/TUI + optional AI
```

OpenStock is built for research, education and market analysis. It is **not** a broker, portfolio manager, investment adviser or trading-execution system.

> **Project status:** active development. Stable architecture and operating procedures are documented in the repository. Current priority, dependency and delivery status are maintained in [GitHub issue #238](https://github.com/duvu/openstock/issues/238).

## Why OpenStock

Vietnamese market research often depends on provider-specific APIs, inconsistent schemas and historical data that can be revised or incomplete. OpenStock addresses those problems through explicit contracts:

- **Provider independence** — data access is routed through typed provider plugins rather than embedded source-specific calls.
- **Canonical datasets** — provider responses are normalized before downstream use.
- **Evidence before narrative** — validated warehouse data and deterministic tools outrank summaries or model prose.
- **Fail-closed behavior** — missing, stale, malformed or unsupported inputs are surfaced explicitly.
- **Reproducible research** — dates, providers, versions, assumptions, lineage and caveats remain inspectable.
- **Point-in-time direction** — historical workflows are designed to avoid survivorship and look-ahead leakage.
- **Optional AI** — deterministic research remains usable when the LLM assistant is disabled.

## Engineering test policy

OpenStock uses a **1:1 public feature/function-to-authoritative-test policy**.

```text
one public feature or public function
→ one authoritative automated test case
```

The policy exists to prevent issue-driven test accumulation and repeated testing of the same behavior across repository, service, CLI, TUI and assistant layers.

- Private helpers and implementation branches do not receive separate tests when their behavior is already covered by the owning public contract.
- Equivalent inputs and edge conditions should be checked inside the same table-driven test where practical; they must not expand into large parameterized test matrices merely to increase test counts.
- High-impact boundaries such as point-in-time exclusion, transaction rollback, queue crash recovery, writer exclusion, policy approval and package state preservation are modeled as separate public risk contracts and therefore may each own one authoritative test.
- Adding a new authoritative test requires a new public contract or replacement of an obsolete test.
- The repository target is approximately 200 authoritative automated tests, with a hard cap of 250.

The normative consolidation and enforcement work is tracked in [issue #348](https://github.com/duvu/openstock/issues/348).

## Repository structure

| Path | Purpose |
|---|---|
| [`vnstock/`](vnstock/) | Data-only Python package and localhost service for market, reference and fundamental data |
| [`vnalpha/`](vnalpha/) | Terminal-first research workspace, DuckDB warehouse, analysis workflows and optional AI assistance |
| [`packaging/`](packaging/) | Debian packaging, systemd units, deployment scripts and operational verification |
| [`openspec/`](openspec/) | Requirements, design decisions, implementation tasks and validation evidence |
| [`scripts/`](scripts/) | Repository consistency and governance checks |
| [`docker-compose.yml`](docker-compose.yml) | Canonical single-host data-service and worker deployment |
| [`ROADMAP.md`](ROADMAP.md) | Stable roadmap policy and pointer to the live GitHub issue queue |

## Architecture
