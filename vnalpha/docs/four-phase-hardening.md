# Four-phase hardening guide

This guide records the operational contract delivered by the
`openstock-four-phase-hardening` change. The product remains a research-only
workspace: it can inspect and explain persisted market data, but it does not
place orders, manage accounts, allocate portfolios, transfer funds, or expose
broker execution.

## Architecture and package boundaries

`vnstock-service` remains the data provider. `vnalpha` owns the warehouse,
workspace context, deterministic research tools, assistant lifecycle, model
routing, TUI, and offline evaluations. The public `vnalpha.cli:app` entrypoint,
safe tool names, and `AssistantApp.ask()` compatibility wrapper remain stable.

The main ownership boundaries are:

- `workspace_context`: storage, locking, lifecycle, retention, compaction,
  redaction, export, and repair;
- `assistant`: typed requests, untrusted historical context, prepared turns,
  policy, planning, execution, synthesis, and research-answer audit;
- `data_availability`: strict dates, readiness checks, cache eligibility, and
  owner-aware data locks;
- `model_routing`: profile resolution, session/workspace overrides, fallback,
  and route observability;
- `evals`: fixture-contract evaluation and runtime replay through production
  assistant boundaries.

## Workspace lifecycle and migration

The canonical workspace root is resolved independently of the shell directory:

1. an explicit root argument;
2. `VNALPHA_WORKSPACE_ROOT`;
3. the platform user-state directory.

Legacy project-local `.vnalpha/workspaces` roots are detected explicitly and
must be migrated with the workspace migration service. Migration rejects
ambiguous multiple legacy roots, preserves a backup, validates state, and does
not silently merge stores.

Mutations use an owner-aware transaction lock. A workspace state is either
`ACTIVE` or `ARCHIVED`; the latest pointer references only an active valid
workspace. `/context status` is read-only. `/context new` compacts or archives
the current active workspace before activating the new one.

`/context compact` performs real bounded retention and writes a compaction
manifest. It preserves pinned artifacts, open tasks, notes, assumptions, and
source references while archiving older entries. Repeating compaction without
new state is idempotent. Context and export projections are redacted and do
not include raw event history by default.

## Assistant lifecycle and dates

`AssistantRequest` keeps the current prompt separate from bounded workspace and
chat context. Historical context is lower-trust auxiliary data; it cannot
select a tool or change the classified intent. `AssistantApp.prepare()` runs
safety, classification, normalization, policy, and planning once. Approval and
execution consume the same immutable prepared turn and plan hash.

An explicit `date` is validated at the assistant boundary before
classification, planning, data provisioning, or tool execution. Valid values
are `today` or ISO `YYYY-MM-DD`. Invalid values raise a user-facing validation
error and persist a validation-error session without calling the classifier.

## Commands, TUI, and model scope

`/new` is the workspace alias for `/context new`. Chat sessions use `/chat new`.
The old chat-local `/new` behavior is not retained. TUI TODO visibility events
are emitted only when visibility changes, including responsive-layout changes.

Model override precedence is explicit:

1. per-call profile;
2. session override;
3. workspace override;
4. stage/task policy;
5. configured default profile.

Session overrides are keyed by chat/session ID and are cleared when a chat
session changes or closes. `/model status` reports the effective session ID and
override scope without exposing prompt content.

## Evaluation and packaging

Fixture-contract evaluation validates static typed observations. Runtime replay
loads strict typed JSON cases, uses deterministic fake LLM responses and seeded
tool outputs, executes `AssistantApp.prepare()` and `execute_prepared()`,
checks plan/traces/policy/groundedness/fallback/audit outcomes, and blocks
network access.

Golden YAML and runtime JSON cases are package resources loaded through
`importlib.resources`. Both wheel and sdist include them. The Debian build
bundles the local application wheel and its resources so the post-install
virtual environment can install `vnalpha` without a network connection.

Run the public evaluation surfaces from the repository root:

```bash
make eval-research-answers
make eval-research-runtime
make verify-hardening
```

The runtime CLI also supports `--json` for machine-readable reports.

## Validation and rollback

The validation ledger is
`openspec/changes/openstock-four-phase-hardening/validation.md`. Each evidence
row identifies the tested tree, exact command, exit code, result summary, and
artifact. `scripts/check-openspec-completion.py` rejects malformed evidence,
pending gates, missing required commands, and unchecked completion-ready tasks.

The phase boundaries are independently reviewable. If a hardening phase must
be rolled back, preserve the workspace backup/quarantine and do not restore
unsafe defaults. Re-run repository hygiene, focused tests, lint, packaging,
fixture evaluation, runtime replay, and the completion verifier before making
the next phase active. Existing rollback and package-removal procedures remain
in `packaging/docs/ROLLBACK.md`.
