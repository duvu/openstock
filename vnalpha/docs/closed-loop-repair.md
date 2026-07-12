# Closed-loop repair and validation

The closed loop is a bounded research-artifact workflow:

```text
RUN -> OBSERVE -> PACKAGE -> AI_FIX -> VALIDATE -> PROMOTE_READY
     -> PROMOTED / REJECTED -> ROLLED_BACK
```

It does not merge production code, access accounts, place orders, allocate
portfolios, or deploy live trading behavior. A repair attempt must be supplied
with an adapter whose `is_sandbox` value is true; the closed-loop service never
executes generated code locally.

## Package boundaries

The implementation lives under `vnalpha/src/vnalpha/closed_loop/`:

- `models.py` defines lifecycle states, repair bundles, proposals, attempts,
  validation reports, and research deployment records.
- `bundle.py` reads failed run evidence and writes a complete typed bundle.
- `proposal.py` and `policy.py` create bounded repair proposals and reject
  execution-like behavior.
- `validation.py` runs the eight promotion checks.
- `deployment.py` verifies, promotes, and rolls back research artifacts.
- `store.py` persists JSON records and lifecycle JSONL; `events.py` writes
  correlated, redacted lifecycle events.

The command registry exposes `/repair`, `/validate`, and `/deploy`. The Typer
surface exposes the same repair and validation operations as `vnalpha repair`
and `vnalpha validate`; deploy commands use the research-artifact gate.

## Repair bundle schema

Bundles are stored under `<log-root>/bundles/<repair-id>/`:

```text
repair-bundle.json       typed diagnostic bundle
manifest.json            section inventory and correlation metadata
repair-state.json        current lifecycle summary
lifecycle.jsonl          state history
closed-loop.jsonl        correlated repair and attempt events
repair-proposal.json     bounded AI proposal, when created
attempts/attempt-N.json  one redacted result per sandbox attempt
```

`repair-bundle.json` contains the repair ID, correlation ID, failed job and
session IDs, request and plan summary, generated code, static guard result,
stdout/stderr, error trace, input dataset references, output manifest/state,
validation result, environment summary, and redaction status.

`/repair prepare --latest` selects the newest run that contains a failed
command or captured exception. `/repair prepare <job-id>` resolves a direct run
or a failed sandbox job directory. `/repair status` reads the durable lifecycle
and attempt history. `/repair propose` persists a scope-limited proposal.

The maximum attempt count defaults to three and can be set between one and ten
with `VNALPHA_MAX_REPAIR_ATTEMPTS`. Exhaustion persists every attempt and sets
the repair lifecycle to `FAILED`.

Repair application accepts only an application-injected sandbox runner whose
`is_sandbox` capability is exactly true. The CLI and TUI fail closed when no
approved runner is available; they never execute generated code locally.

## Validation gate

`/validate run <artifact-id>` persists a report under
`<log-root>/validations/<artifact-id>.json` and, when an artifact path is known,
`validation-report.json` beside the artifact. Promotion requires all of these
checks to pass:

1. static guard;
2. sandbox execution evidence;
3. output schema (`result.json` and non-empty `summary.md`);
4. artifact manifest and type;
5. lineage;
6. quality status;
7. caveats;
8. read-only boundary.

Missing lineage or caveats is a failed gate, not a warning. Generated code is
assessed by the existing sandbox static guard and by the closed-loop boundary
policy. The persisted report also records the confined artifact root and a
content digest; promotion recomputes both before writing a promotion marker.
Closed-loop IDs and artifact trees are confined to the configured evidence
root, including symlink resolution.

## Research deploy log semantics

Promotable types are indicator definitions, feature definitions, experiment
templates, pattern scanner definitions, and offline event-study templates.

`/deploy verify <candidate>` writes a verification record under
`<log-root>/deployments/<deployment-id>-verification.json`. It succeeds only
when the candidate has a passing validation report, a recognized manifest type,
and a passing read-only check.

`/deploy promote <candidate> --deployment-id <id>` writes the promotion state
to `<log-root>/deployments/<id>.json` and a `promotion.json` marker in the
research artifact. `/deploy rollback <id>` changes only that artifact marker
and deployment state. Both actions emit events to the artifact's closed-loop
JSONL log and preserve the validation correlation ID.

No `--force` path exists in the closed-loop command layer. A failed validation
or boundary check is terminal for that promotion attempt.

## Observability events

The event stream includes:

```text
REPAIR_BUNDLE_CREATED
REPAIR_PROPOSAL_CREATED
REPAIR_ATTEMPT_STARTED
REPAIR_ATTEMPT_SUCCEEDED / REPAIR_ATTEMPT_FAILED
VALIDATION_STARTED
VALIDATION_SUCCEEDED / VALIDATION_FAILED
RESEARCH_ARTIFACT_PROMOTED
RESEARCH_ARTIFACT_ROLLED_BACK
```

Every event carries a correlation ID and default redaction status. Attempt
streams and repair bundle text are redacted before persistence unless the
operator explicitly selects the existing full-content logging mode.

## Manual smoke path

Use an isolated writable log root when running the CLI locally:

```bash
export VNALPHA_LOG_ROOT=/tmp/openstock-closed-loop
export VNALPHA_LOG_PATH=/tmp/openstock-closed-loop/vnalpha.log
vnalpha repair prepare --latest
vnalpha repair status <repair-id>
vnalpha repair propose <repair-id>
vnalpha validate run <artifact-id> --artifact-root <artifact-path>
vnalpha deploy verify <artifact-id>
vnalpha deploy promote <artifact-id> --deployment-id <deployment-id>
vnalpha deploy rollback <deployment-id> --reason "research review"
```
