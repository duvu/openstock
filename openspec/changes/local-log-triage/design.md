## Context

`vnalpha logs` presents a single structured application run, while local service
and CI failures remain separate text sources. Codex needs a bounded, repeatable
way to collect failure evidence without mutating the workspace or exposing
credentials copied into logs.

## Goals / Non-Goals

**Goals:**

- Analyze explicit files and deterministic workspace log discovery using only the
  standard library.
- Parse OpenStock JSONL records and plain-text logs into one typed finding model.
- Deduplicate repeated failures, redact sensitive values, and offer a next command
  that preserves the evidence-first debugging workflow.
- Fetch only failed output for an explicit GitHub Actions run through the locally
  authenticated `gh` CLI.

**Non-Goals:**

- No service control, file mutation, GitHub writes, provider calls, or automatic
  remediation.
- No unrestricted recursive filesystem scan, credential display, or raw exception
  dump.
- No replacement for the `vnalpha logs` per-run application UI.

## Decisions

### Standalone standard-library script

Place `openstock-log-triage.py` under `scripts/` so Codex can execute it from the
repository without importing `vnalpha` or requiring a configured application
environment. A standalone script avoids coupling operational diagnosis to a
potentially broken package install.

### Explicit and bounded sources

The script accepts repeatable `--path` values and otherwise discovers only `*.log`
files under `ya-router/logs` and structured logs under the configured `VNALPHA_LOG_ROOT`
or the documented local fallback. An explicit numeric `--github-run` optionally
calls `gh run view <id> --log-failed`; it never discovers, merges, reruns, or writes
to GitHub.

### Conservative analysis model

Use a finite severity/category mapping over JSONL error metadata and plain-text
signals. Findings preserve source and line number, collapse duplicate signatures,
redact sensitive assignments/URLs, and emit a short source-aware diagnostic command
instead of claiming a root cause.

### Stable output contract

Markdown is the default for Codex and operators; `--json` exposes the same bounded
finding fields for automation. The normal exit status reports successful analysis;
`--fail-on-findings` makes detected errors a caller-controlled non-zero outcome.

### Project debugging rule

The repository `AGENTS.md` is the Codex-facing entry point for this workflow. It
requires a default triage invocation before source-level debugging, requires
explicit local/CI source selection when known, and preserves the tool as evidence
rather than a substitute for runtime reproduction or manual QA.

## Risks / Trade-offs

- [Unrecognized log format] → retain a sanitized `RUNTIME` finding rather than
  dropping a matched error line.
- [Secret in text log] → apply redaction before deduplication and every renderer.
- [Missing `gh` or unavailable run] → emit a local diagnostic finding and continue
  with other sources.
- [Very large log] → read only the final bounded number of lines per source.

## Migration Plan

The script is additive. Existing `vnalpha logs` commands and workflow behavior are
unchanged; operators can adopt the script immediately or remove it without state
migration.
