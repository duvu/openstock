# Proposal: Closed-loop repair and validation for auto research

## Summary

Add OpenSpec for Phase D of the production/MVP2 OpenStock roadmap:

```text
Phase D: Closed-loop Repair and Validation
```

This phase closes the loop for the opencode-like auto research system:

```text
RUN -> OBSERVE -> PACKAGE -> AI FIX -> VALIDATE -> PROMOTE/REJECT -> DEPLOY LOG -> REPEAT
```

The system remains inside the read-only research boundary.

## Why

After the system can run sandboxed research jobs and structured experiments, production-readiness depends on whether failures are diagnosable, repairable, and validated.

The goal is not to let the agent freely change production behavior. The goal is to make research computation and research artifacts self-healing within strict boundaries:

```text
failed sandbox job
  -> collect logs/artifacts/context
  -> prepare repair bundle
  -> propose code/data/prompt fix
  -> re-run validation in sandbox
  -> promote or reject research artifact
  -> log decision
```

## Goals

- Add repair bundle generation for failed sandbox/research automation jobs.
- Add AI-assisted repair proposal workflow.
- Add bounded repair retry loop.
- Add validation gate for repaired research artifacts.
- Add promote/reject workflow for validated research artifacts.
- Add deploy log for research artifact promotion only.
- Add `/repair`, `/validate`, and `/deploy` production semantics.
- Preserve read-only research boundary.
- Preserve closed-loop logging and redaction-by-default.

## Non-goals

- No automatic production code merge.
- No automatic GitHub PR merge.
- No broker/order/account/portfolio/margin/trading execution.
- No live strategy deployment.
- No modification to live trading systems.
- No unrestricted AI patching outside sandbox-generated research artifacts unless explicitly implemented in a separate code-review workflow.

## Scope

### Closed-loop lifecycle

The implementation SHALL support this lifecycle:

```text
RUN
OBSERVE
PACKAGE
AI_FIX
VALIDATE
PROMOTE_OR_REJECT
DEPLOY_LOG
REPEAT
```

For OpenStock, `DEPLOY_LOG` means logging research artifact promotion/rollback status. It does not mean trading execution deployment.

### Repair bundle

Repair bundles SHALL include:

```text
repair_id
correlation_id
failed job/session id
user request
plan summary
generated code
static guard result
stdout/stderr
error trace
input dataset references
output artifact state
validation result
environment summary
redaction status
```

### AI fix proposal

The AI fix workflow SHALL produce patch proposals for sandbox research code, experiment definitions, feature definitions, or validation schemas.

It SHALL NOT change broker/order/account/portfolio/margin/trading execution code because such code must not exist in this product boundary.

### Validation gate

Before a repaired artifact can be promoted, the system SHALL validate:

```text
static guard pass
sandbox execution pass
output schema pass
artifact manifest pass
lineage present
quality status present
caveats present
read-only boundary pass
```

### Promotion and rollback

Promotion SHALL apply only to research artifacts such as:

```text
approved indicator definition
approved feature definition
approved experiment template
approved pattern scanner definition
approved offline event-study template
```

Rollback SHALL revert research artifact promotion state and log the decision.

## Success criteria

This phase is complete only when:

```text
- `/repair prepare --latest` packages latest failed sandbox/research job.
- `/repair status <repair-id>` shows repair lifecycle status.
- AI repair proposal is generated from a repair bundle.
- Repair retry loop is bounded by max attempts.
- Repaired jobs re-run only inside sandbox.
- `/validate run <artifact-id>` validates research artifacts.
- `/deploy verify <candidate>` verifies promotion readiness.
- `/deploy promote <candidate> --deployment-id <id>` promotes research artifact only.
- `/deploy rollback <deployment-id>` rolls back research artifact promotion only.
- Every step emits closed-loop observability events.
- read-only research boundary is preserved.
```

## Validation commands

Run:

```bash
make test-vnalpha
make lint-vnalpha
make verify-r4
openstock-verify --ci
pytest vnalpha/tests -k "repair or validate or deploy or closed_loop"
```

## Production boundary

Closed-loop repair is allowed to repair research jobs and research artifacts.

It SHALL NOT perform broker integration, order execution, live portfolio changes, account access, margin activity, transfer activity, or trading execution deployment.
