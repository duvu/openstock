## Why

OpenStock logs are split between structured `vnalpha` run records, local service
logs, and failed GitHub Actions output. Investigating a failure currently requires
manual, source-specific searches, which slows safe diagnosis and can expose noisy
or sensitive text to an assistant.

## What Changes

- Add a read-only `openstock-log-triage` repository script for local and failed
  GitHub Actions log inspection.
- Normalize matching log records into bounded, deduplicated findings with source,
  severity, category, sanitized evidence, and a next diagnostic command.
- Provide human-readable Markdown by default and machine-readable JSON on demand.
- Support explicit file paths, deterministic workspace log discovery, and an
  optional explicit GitHub Actions run ID through the authenticated `gh` CLI.
- Require Codex debugging workflows in this repository to collect triage output
  before source-level diagnosis.

## Capabilities

### New Capabilities

- `local-log-triage`: bounded, redaction-safe analysis of OpenStock local logs and
  explicitly selected failed GitHub Actions output.

### Modified Capabilities

- None.

## Impact

- Adds one standard-library Python script under `scripts/` and one owning contract
  test under `scripts/tests/`.
- Does not modify application logging, invoke services, create files, change GitHub
  state, or access providers. GitHub inspection is opt-in and read-only.
- The change is proposed locally without a GitHub issue; it remains unscheduled
  until a maintainer associates it with the roadmap.
