# Review: Closed-loop logging and AI repair gap analysis

## Verdict

The current implementation is a strong start for file-based observability, but it is not yet a 100% closed-loop improvement system.

Approximate state:

```text
File-based observability foundation: 70-80%
AI-readable support bundle:         60-70%
Repair bundle and repair tracking:   0-15%
Deploy gate / promote / rollback:    0-15%
End-to-end closed loop:             35-50%
```

The next implementation should avoid adding more documentation-only claims. It should focus on runtime behavior, tests, and evidence.

## Current strengths

- Run directory model exists.
- JSONL writer exists and is best-effort.
- Redaction helper exists with metadata/redacted/full modes.
- Audit, app, error, trace, and command writer helpers exist.
- Summary generation exists.
- Log bundle generation exists.
- `vnalpha logs` command group exists.
- Some chat/tool/domain/script instrumentation exists.

## Blocking gaps

### 1. Correlation IDs are split

The CLI uses `vnalpha.core.logging.set_correlation_id()`, while observability event writers read `vnalpha.observability.context.get_correlation_id()`.

This can cause file-based observability events to have `correlation_id="unset"`, even when structlog events have a valid correlation ID.

Impact:

```text
AI agent cannot reliably reconstruct one command/chat/tool/pipeline flow.
```

### 2. Audit call-site mismatch

Some runtime call sites pass `module=` to `log_audit()`, but the writer does not accept that parameter.

Because calls are wrapped in broad `except Exception`, affected audit events can silently disappear.

Impact:

```text
Important events such as TOOL_REFUSED or assistant answer logs may not exist in audit.jsonl.
```

### 3. CLI command lifecycle is not uniformly logged

The CLI callback initializes logging, but major commands are not consistently wrapped with:

```text
COMMAND_STARTED
COMMAND_SUCCEEDED
COMMAND_FAILED
```

Impact:

```text
AI agent may see app startup but not the exact command lifecycle, exit status, duration, or failure reason.
```

### 4. Shell scripts log too coarsely

Pipeline/verify/backup scripts write some JSONL, but they do not fully log step/check/failure lifecycles.

Required behavior:

```text
pipeline step started/succeeded/failed
verify check pass/warn/skip/fail
backup lock failure/missing warehouse/copy failure/success
```

### 5. Bundle is a log bundle, not a repair bundle

The current bundle is useful for support handoff, but it is not sufficient as a coding-agent repair package.

Missing:

```text
ai-coding-prompt.md
reproduction.md
rich manifest.json
source commit SHA
required validation commands
guardrails
expected coding-agent output format
```

### 6. Repair lifecycle is absent

No runtime `repair` command group is present yet.

Missing:

```text
vnalpha repair prepare --latest
vnalpha repair status <repair-id>
vnalpha repair validate <repair-id>
REPAIR_PREPARED / REPAIR_VALIDATION_* events
```

### 7. Deploy lifecycle is absent

No runtime deploy gate command group is present yet.

Missing:

```text
vnalpha deploy verify
vnalpha deploy promote <candidate>
vnalpha deploy rollback <deployment-id>
DEPLOY_VERIFY_* / DEPLOY_BLOCKED / DEPLOY_PROMOTED / ROLLBACK_* events
```

### 8. No closed-loop fixture exists

There is no test scenario proving:

```text
fixture failure -> logs -> repair bundle -> validation -> promotion blocked/pass -> event trail
```

Without this, the system cannot claim closed-loop improvement readiness.

## Implementation risks

### Risk: marking tasks complete prematurely

Prior OpenSpec tasks marked several areas complete even where runtime evidence is partial. This change must require code/test/script evidence before marking completion.

### Risk: logging becomes noisy but not actionable

The solution should prioritize actionable lifecycle events and AI-readable summaries rather than dumping every UI event.

### Risk: AI prompt leaks secrets

Repair bundles and coding prompts must use redaction by default. Full mode must remain explicit opt-in.

### Risk: unsafe auto-deploy loop

The repair loop must be AI-assisted, not uncontrolled. Promotion must be gated by tests and verification.

## Recommended target architecture

```text
observability core
  -> unified correlation context
  -> JSONL event writers
  -> command lifecycle wrapper
  -> script JSONL helper

logs command group
  -> latest/show/errors/summarize/doctor/bundle

repair command group
  -> prepare/status/validate
  -> repair bundles
  -> repair event logging

deploy command group
  -> verify/promote/rollback
  -> deploy event logging
  -> validation gate enforcement
```

## Minimum evidence before claiming 100%

```text
make test-vnalpha
make lint-vnalpha
make verify-r0
make verify-r2-ci
make verify-r4
openstock-verify --ci
script syntax checks
fixture failed command -> repair bundle test
promotion blocked on failed/missing validation test
repair/deploy event files inspected in tests
```
